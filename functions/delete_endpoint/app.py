import boto3
import botocore

sagemaker_client = boto3.client('sagemaker')

def handler(event, context):
    # Get endpoint name
    endpoint_name = event['EndpointName']

    # Check if endpoint exists
    try:
        print("Checking if endpoint exists")
        # Check endpoint exist
        describe_response = sagemaker_client.describe_endpoint(
            EndpointName=endpoint_name
        )

        # Endpoint exists, delete endpoint
        print("Endpoint exists, Deleting endpoint")
        sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
        print("Endpoint deleted")
    except botocore.exceptions.ClientError as error:
        # Endpoint does not exist, create endpoint
        print("Endpoint does not exist")
        pass