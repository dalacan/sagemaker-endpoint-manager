import boto3
import botocore
import os
from datetime import datetime
import json

sagemaker_client = boto3.client('sagemaker')
ssm_client = boto3.client("ssm")
SSM_ENDPOINT_EXPIRY_PARAMETER = os.environ['SSM_ENDPOINT_EXPIRY_PARAMETER']

def create_endpoint(endpoint_name, endpoint_config_name):
    return sagemaker_client.create_endpoint(
                                        EndpointName=endpoint_name, 
                                        EndpointConfigName=endpoint_config_name) 

def handler(event, context):

    # Get expiry
    expiry_parameter = ssm_client.get_parameter(Name=SSM_ENDPOINT_EXPIRY_PARAMETER)
    expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])
    expiry = datetime.strptime(expiry_parameter_values['expiry'], '%d-%m-%Y-%H-%M-%S')
    now = datetime.utcnow()
    
    # Expired, delete endpoint
    if expiry < now:
        print("Endpoint has expired")
        # Delete endpoint
        print("Deleting endpoint")
        sagemaker_client.delete_endpoint(EndpointName=expiry_parameter_values['endpoint_name'])
    else:
        # Check if endpoint is expiring
        print("Endpoint is not expiring")
        try:
            print("Checking if endpoint exists")
            # Check endpoint exist
            describe_response = sagemaker_client.describe_endpoint(
                EndpointName=expiry_parameter_values['endpoint_name']
            )
        except botocore.exceptions.ClientError as error:
            # Endpoint does not exist, create endpoint
            if error.response['Error']['Code'] == 'ValidationException':
                print("Creating endpoint")
                create_endpoint_response = create_endpoint(expiry_parameter_values['endpoint_name'], expiry_parameter_values['endpoint_config_name'])

            print(error)


    
