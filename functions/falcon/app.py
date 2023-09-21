import os
import boto3

# grab environment variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
client = boto3.client('runtime.sagemaker')

def handler(event, context):

    payload = event['body']

    try:
        params = {
            "Accept": "application/json",
            "Body": payload,
            "ContentType": "application/json",
            "EndpointName": ENDPOINT_NAME,
        }
        if "headers" in event and "X-Amzn-SageMaker-Custom-Attributes" in event["headers"]:
            params["CustomAttributes"] = event["headers"]["X-Amzn-SageMaker-Custom-Attributes"]
        response = client.invoke_endpoint(**params)

        result = {
            "statusCode": 200,
            "headers": {
                    'Content-Type': 'text/json'
                        },
            "body": response["Body"].read()
        }
    except Exception as e:
        result = {
            "statusCode": 500,
            "headers": {
                    'Content-Type': 'text/json'
                        },
            "body": str(e)
        }

    return result
