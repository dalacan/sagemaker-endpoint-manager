import os
import boto3
import botocore
import json

from datetime import datetime, timedelta

# grab environment variables
ssm_client = boto3.client("ssm")
SSM_ENDPOINT_EXPIRY_PARAMETER = os.environ['SSM_ENDPOINT_EXPIRY_PARAMETER']

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

def get_endpoint_expiry_info(event):
    if event['queryStringParameters'] is not None and 'EndpointName' in event['queryStringParameters']:
        print("Getting specific endpoint")
        # Get expiry
        expiry_parameter = ssm_client.get_parameter(
            Name=f"/sagemaker/endpoint/expiry/{event['queryStringParameters']['EndpointName']}",
            WithDecryption=False)
        expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])
        
        endpoint_expiry_info = get_expiry(expiry_parameter_values)

        response =  {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(endpoint_expiry_info)
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
        endpoint_expiry_info = []
        for parameter in result:
            print("Processing endpoint")
            parameter_values = json.loads(parameter['Value'])
            endpoint_expiry_info.append(get_expiry(parameter_values))

        response =  {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(endpoint_expiry_info)
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

def create_update_endpoint_expiry(event):
    if event['body'] is not None :
        # Update expiry
        body = json.loads(event["body"])

        if 'EndpointName' not in body:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "EndpointName required"})
            }
            return response

        try:
            endpoint_name = body['EndpointName']
            expiry_parameter = ssm_client.get_parameter(
                    Name=f"/sagemaker/endpoint/expiry/{endpoint_name}",
                    WithDecryption=False)
            
            expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])

            print("Updating endpoint")
            time_left, expiry_str = update_endpoint_config(endpoint_name, body['minutes'], expiry_parameter_values)

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
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ParameterNotFound':
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
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Error retrieving endpoint"})
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
        response = create_update_endpoint_expiry(event)
    else:
        # Return an error message for unsupported methods
        response = {
            "statusCode": 405,
            "body": json.dumps({"error": "Method not allowed"})
        }
    return response