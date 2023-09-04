import boto3
import botocore
import json

from datetime import datetime, timedelta

ssm_client = boto3.client("ssm")

def get_expiry(expiry_parameter_values):
    expiry = datetime.strptime(expiry_parameter_values['expiry'], '%d-%m-%Y-%H-%M-%S')
    now = datetime.utcnow()
    time_left = expiry - now


    endpoint_expiry_info = {
        "EndpointName": expiry_parameter_values['endpoint_name'],
        "EndpointExpiry ": expiry_parameter_values['expiry'],
        "TimeLeft": str(time_left)
    }

    return endpoint_expiry_info

def get_schedule(parameter_values):
    schedule = {
        "EndpointName": parameter_values['endpoint_name'],
        "Schedule": parameter_values['schedule']
    }

    return schedule

def get_endpoint_expiry_info(event):
    if event['queryStringParameters'] is not None and 'EndpointName' in event['queryStringParameters']:
        print("Getting specific endpoint")
        # Get expiry
        expiry_parameter = ssm_client.get_parameter(
            Name=f"/sagemaker/endpoint/expiry/{event['queryStringParameters']['EndpointName']}",
            WithDecryption=False)
        parameter_values = json.loads(expiry_parameter['Parameter']['Value'])
        
        if 'expiry' in parameter_values:
            endpoint_info = get_expiry(parameter_values)

        if 'schedule' in parameter_values:
            endpoint_info = get_schedule(parameter_values)

        response =  {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(endpoint_info)
        }
    else:
        print("Getting list of endpoint expiry")
        # Get a list of endpoint expiry parameters
        ssm_response = ssm_client.get_parameters_by_path(
            Path="/sagemaker/endpoint/expiry/",
            Recursive=True)
        result = ssm_response["Parameters"]

        
        while "NextToken" in ssm_response:
            ssm_response = ssm_client.get_parameters_by_path(
                Path="/sagemaker/endpoint/expiry/",
                Recursive=True,
                NextToken=result["NextToken"])
            result.extend(ssm_response["Parameters"])

        # Process each endpoint expiry configuration
        endpoint_info = []
        for parameter in result:
            print("Processing endpoint")
            parameter_values = json.loads(parameter['Value'])

            if 'expiry' in parameter_values:
                # endpoint_expiry_info = get_expiry(parameter_values)
                endpoint_info.append(get_expiry(parameter_values))

            if 'schedule' in parameter_values:
                endpoint_info.append(get_schedule(parameter_values))
            

        response =  {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(endpoint_info)
        }

    return response

def create_endpoint_config(endpoint_name, endpoint_config_name, provision_minutes):
    now = datetime.utcnow()
    expiry = now + timedelta(minutes=provision_minutes)
    expiry_str = expiry.strftime("%d-%m-%Y-%H-%M-%S")

    expiry_ssm_value = {
        "expiry": expiry_str,
        "endpoint_name": endpoint_name,
        "endpoint_config_name": endpoint_config_name
    }

    # Add new parameter
    ssm_response = ssm_client.put_parameter(
        Name=f"/sagemaker/endpoint/expiry/{endpoint_name}",
        Type="String",
        Overwrite=True,
        Value=json.dumps(expiry_ssm_value)
    )

    return provision_minutes, expiry_str

def update_endpoint_config(endpoint_name, provision_minutes, expiry_parameter_values):
    current_expiry = datetime.strptime(expiry_parameter_values['expiry'], '%d-%m-%Y-%H-%M-%S')

    # Check if current expiry is in the past
    now = datetime.utcnow()
    if current_expiry < now:
        current_expiry = now

    expiry = current_expiry + timedelta(minutes=provision_minutes)
    expiry_str = expiry.strftime("%d-%m-%Y-%H-%M-%S")

    time_left = expiry - now

    expiry_parameter_values['expiry'] = expiry_str

    # Update parameter
    ssm_response = ssm_client.put_parameter(
        Name=f"/sagemaker/endpoint/expiry/{endpoint_name}",
        Overwrite=True,
        Value=json.dumps(expiry_parameter_values)
    )
     
    return time_left, expiry_str

def create_update_endpoint_config_schedule(endpoint_name, endpoint_config_name, schedule):
    ssm_value = {
        "schedule": schedule,
        "endpoint_name": endpoint_name,
        "endpoint_config_name": endpoint_config_name
    }

    # Add new parameter
    ssm_response = ssm_client.put_parameter(
        Name=f"/sagemaker/endpoint/expiry/{endpoint_name}",
        Type="String",
        Overwrite=True,
        Value=json.dumps(ssm_value)
    )

def get_endpoint_config_parameters(endpoint_name):
    try:
        # Get endpoint configuration
        ssm_parameters = ssm_client.get_parameter(
                Name=f"/sagemaker/endpoint/expiry/{endpoint_name}",
                WithDecryption=False)
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'ParameterNotFound':
            return False
        else:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "Error retrieving endpoint"})
            }

    return ssm_parameters

def create_update_endpoint_schedule(event):
    if event['body'] is not None :
        # Update expiry
        body = json.loads(event["body"])

        if 'EndpointName' not in body:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "EndpointName required"})
            }
            return response

        endpoint_name = body['EndpointName']
        endpoint_parameters = get_endpoint_config_parameters(endpoint_name)
        
        # Check if a schedule was provided
        if "schedule" in body:
            # Update schedule
            if endpoint_parameters is False:
                # Endpoint ssm parameters does not exist
                if 'EndpointConfigName' in body:
                    print("Creating new endpoint config")
                    endpoint_config_name = body['EndpointConfigName']
            else:
                print("Updating schedule")
                endpoint_parameters_values = json.loads(endpoint_parameters['Parameter']['Value'])
                endpoint_config_name = endpoint_parameters_values['endpoint_config_name']

            
            # Create/Update schedule
            create_update_endpoint_config_schedule(endpoint_name, endpoint_config_name, body['schedule'])

            response =  {
                            "statusCode": 200,
                            "headers": {
                                "Content-Type": "application/json"
                            },
                            "body": json.dumps({
                                "EndpointName": endpoint_name,
                                "Schedule": body['schedule']
                            })
                        }


        elif "minutes" in body:
            # Update provision expiry
            if endpoint_parameters is False:
                # Endpoint ssm parameters does not exist
                if 'EndpointConfigName' in body:
                    print("Creating new endpoint config")
                    time_left, expiry_str = create_endpoint_config(endpoint_name, body['EndpointConfigName'], body['minutes'])

                    response =  {
                        "statusCode": 200,
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "body": json.dumps({
                            "EndpointName": endpoint_name,
                            "EndpointExpiry ": expiry_str,
                            "TimeLeft": str(time_left)
                        })
                    }
                else:               
                    response = {
                        "statusCode": 400,
                        "body": json.dumps({"error": "EndpointName not found/Endpoint config name required"})
                    }
            else:                           
                print("Updating endpoint configurations")
                endpoint_parameters_values = json.loads(endpoint_parameters['Parameter']['Value'])
                time_left, expiry_str = update_endpoint_config(endpoint_name, body['minutes'], endpoint_parameters_values)

                response =  {
                            "statusCode": 200,
                            "headers": {
                                "Content-Type": "application/json"
                            },
                            "body": json.dumps({
                                "EndpointName": endpoint_name,
                                "EndpointExpiry ": expiry_str,
                                "TimeLeft": str(time_left)
                            })
                        }
    else:
        response = {
            "statusCode": 400,
            "body": json.dumps({"error": "Body required"})
        }

    return response

def handler(event, context):
    http_method = event['httpMethod']

    if http_method == "GET":
        response = get_endpoint_expiry_info(event)
    elif http_method == "POST":
        response = create_update_endpoint_schedule(event)
    else:
        # Return an error message for unsupported methods
        response = {
            "statusCode": 405,
            "body": json.dumps({"error": "Method not allowed"})
        }
    return response