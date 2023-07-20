import os
import boto3

# grab environment variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
runtime= boto3.client('runtime.sagemaker')

def handler(event, context):

    payload = event['body']

    client = boto3.client('runtime.sagemaker')
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
    
    return result