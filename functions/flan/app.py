import os
import json
import boto3

# grab environment variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
runtime= boto3.client('runtime.sagemaker')

def handler(event, context):
    payload = {'text_inputs':'write a sentence to suggest providing a custom input for the model inference', 'max_length': 50, 'temperature': 0.0, 'seed': 321}
    if event['body'] is not None :
        body = event['body']
    else:
        body = json.dumps(payload)

    try:
        response = runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            Body=body,
            ContentType='application/json',
            Accept='application/json'    )

        response = response["Body"].read().decode('utf-8')

        result = {
            "statusCode": 200,
            "headers": {
                    'Content-Type': 'text/json'
                        },
            "body": response
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
