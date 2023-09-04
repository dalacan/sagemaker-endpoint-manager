import boto3
import botocore

sagemaker_client = boto3.client('sagemaker')

def create_endpoint(endpoint_name, endpoint_config_name):
    print("Creating endpoint")
    try:
        sagemaker_client.create_endpoint(
                                    EndpointName=endpoint_name, 
                                    EndpointConfigName=endpoint_config_name)

        # Create paired eventbridge rule to shutdown endpoint
    except botocore.exceptions.ClientError as error:
        print("Error creating endpoint")
        print(error)

def handler(event, context):
    # Get endpoint name
    endpoint_name = event['EndpointName']
    endpoint_config_name = event['EndpointConfigName']

    # Check if endpoint exists
    try:
        print("Checking if endpoint exists")
        # Check endpoint exist
        describe_response = sagemaker_client.describe_endpoint(
            EndpointName=endpoint_name
        )

        # Check if endpoint creation failed, it it has, delete it so that it can be re-created
        if describe_response['EndpointStatus'] == 'Failed':
            print("Endpoint creation failed, deleting endpoint")
            sagemaker_client.delete_endpoint(EndpointName=endpoint_name)

            print("Recreating endpoint")
            create_endpoint(endpoint_name, endpoint_config_name)
        else:
            print("Endpoint is exists, no action required.")

    except botocore.exceptions.ClientError as error:
        # Endpoint does not exist, create endpoint
        if error.response['Error']['Code'] == 'ValidationException':
            create_endpoint(endpoint_name, endpoint_config_name)
        else:
            print("Error describing endpoint")
            print(error)