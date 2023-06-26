import os
import boto3
import json

from datetime import datetime, timedelta

# grab environment variables
ssm_client = boto3.client("ssm")
SSM_ENDPOINT_EXPIRY_PARAMETER = os.environ['SSM_ENDPOINT_EXPIRY_PARAMETER']

def handler(event, context):
    http_method = event['httpMethod']

    if http_method == "GET":
        # Get expiry
        expiry_parameter = ssm_client.get_parameter(
            Name=SSM_ENDPOINT_EXPIRY_PARAMETER,
            WithDecryption=False)
        expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])
        expiry = datetime.strptime(expiry_parameter_values['expiry'], '%d-%m-%Y-%H-%M-%S')
        now = datetime.utcnow()
        time_left = expiry - now

        response =  {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "EndpointExpiry ": expiry_parameter['Parameter']['Value'],
                "TimeLeft": str(time_left)
            })
        }
    elif http_method == "POST":
        if event['body'] is not None :
            # Update expiry
            body = json.loads(event["body"])

            expiry_parameter = ssm_client.get_parameter(
                    Name=SSM_ENDPOINT_EXPIRY_PARAMETER,
                    WithDecryption=False)
            
            expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])
        
            current_expiry = datetime.strptime(expiry_parameter_values['expiry'], '%d-%m-%Y-%H-%M-%S')

            # Check if current expiry is in the past
            now = datetime.utcnow()
            if current_expiry < now:
                current_expiry = now
        
            expiry = current_expiry + timedelta(minutes=body['minutes'])
            expiry_str = expiry.strftime("%d-%m-%Y-%H-%M-%S")

            time_left = expiry - now

            expiry_parameter_values['expiry'] = expiry_str

            # Update parameter
            ssm_response = ssm_client.put_parameter(
                Name=SSM_ENDPOINT_EXPIRY_PARAMETER,
                Overwrite=True,
                Value=json.dumps(expiry_parameter_values)
            )

            response =  {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "EndpointExpiry ": expiry_str,
                    "TimeLeft": str(time_left)
                })
            }
        else:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "Body required"})
            }
    else:
        # Return an error message for unsupported methods
        response = {
            "statusCode": 405,
            "body": json.dumps({"error": "Method not allowed"})
        }
    return response