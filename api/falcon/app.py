import os
import boto3
import json


# grab environment variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
runtime= boto3.client('runtime.sagemaker')

def handler(event, context):
    
    data = json.loads(json.dumps(event))
    payload = json.loads(data['body'])

    client = boto3.client('runtime.sagemaker')
    response = client.invoke_endpoint(
        EndpointName=ENDPOINT_NAME, 
        ContentType='application/json', 
        Body=json.dumps(payload).encode('utf-8')
    )

    result = {
        "statusCode": 200,
        "headers": {
                'Content-Type': 'text/json'
                    },
        "body": json.dumps(
            json.loads(response["Body"].read())
            )
    }
    
    return result