import os
import boto3

# grab environment variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
client = boto3.client('runtime.sagemaker')

def handler(event, context):

    payload = event['body']

    try:
        response = client.invoke_endpoint(
            EndpointName=ENDPOINT_NAME, 
            ContentType='application/json',
            Accept='application/json',
            Body=payload
        )

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
