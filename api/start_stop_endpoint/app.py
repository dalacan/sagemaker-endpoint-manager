import boto3
import botocore
import os
from datetime import datetime

sagemaker_client = boto3.client('sagemaker')
ssm_client = boto3.client("ssm")
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
ENDPOINT_CONFIG_NAME = os.environ['ENDPOINT_CONFIG_NAME']

def create_endpoint(endpoint_name, endpoint_config_name):
    return sagemaker_client.create_endpoint(
                                        EndpointName=endpoint_name, 
                                        EndpointConfigName=endpoint_config_name) 

def handler(event, context):

    # Get expiry
    expiry_parameter = ssm_client.get_parameter(Name=f"{ENDPOINT_NAME}-expiry")
    expiry = datetime.strptime(expiry_parameter['Parameter']['Value'], '%d-%m-%Y-%H-%M-%S')
    now = datetime.utcnow()
    
    # Expired, delete endpoint
    if expiry < now:
        print("Endpoint has expired")
        # Delete endpoint
        print("Deleting endpoint")
        sagemaker_client.delete_endpoint(EndpointName=ENDPOINT_NAME)
    else:
        # Check if endpoint is expiring
        print("Endpoint is not expiring")
        try:
            print("Checking if endpoint exists")
            # Check endpoint exist
            describe_response = sagemaker_client.describe_endpoint(
                EndpointName=ENDPOINT_NAME
            )
        except botocore.exceptions.ClientError as error:
            # Endpoint does not exist, create endpoint
            if error.response['Error']['Code'] == 'ValidationException':
                print("Creating endpoint")
                create_endpoint_response = create_endpoint(ENDPOINT_NAME, ENDPOINT_CONFIG_NAME)

            print(error)


    
