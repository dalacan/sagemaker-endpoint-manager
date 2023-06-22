import os
import boto3
import json

from datetime import datetime, timedelta

# grab environment variables
ssm_client = boto3.client("ssm")
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']

def handler(event, context):
    http_method = event['httpMethod']

    if http_method == "GET":
        # Get expiry
        expiry_parameter = ssm_client.get_parameter(
            Name=f"{ENDPOINT_NAME}-expiry",
            WithDecryption=False)
        
        expiry = datetime.strptime(expiry_parameter['Parameter']['Value'], '%d-%m-%Y-%H-%M-%S')
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
                    Name=f"{ENDPOINT_NAME}-expiry",
                    WithDecryption=False)
        
            current_expiry = datetime.strptime(expiry_parameter['Parameter']['Value'], '%d-%m-%Y-%H-%M-%S')
            now = datetime.utcnow()
            expiry = current_expiry + timedelta(minutes=body['minutes'])
            expiry_str = expiry.strftime("%d-%m-%Y-%H-%M-%S")

            time_left = expiry - now

            # Update parameter
            ssm_response = ssm_client.put_parameter(
                Name=f"{ENDPOINT_NAME}-expiry",
                Overwrite=True,
                Value=expiry_str)

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