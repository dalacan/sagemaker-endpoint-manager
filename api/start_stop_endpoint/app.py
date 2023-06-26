import boto3
import botocore
import os
from datetime import datetime
import json

sagemaker_client = boto3.client('sagemaker')
ssm_client = boto3.client("ssm")
SSM_ENDPOINT_EXPIRY_PARAMETER = os.environ['SSM_ENDPOINT_EXPIRY_PARAMETER']

def start_stop_endpoint(expiry_parameter_values):
    expiry = datetime.strptime(expiry_parameter_values['expiry'], '%d-%m-%Y-%H-%M-%S')
    now = datetime.utcnow()
    
    # Expired, delete endpoint
    if expiry < now:
        print("Endpoint has expired")
        # Delete endpoint
        print("Deleting endpoint")
        try:
            sagemaker_client.delete_endpoint(EndpointName=expiry_parameter_values['endpoint_name'])
        except botocore.exceptions.ClientError as error:
            print("Error deleting endpoint")
            print(error)
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
                try:
                    create_endpoint_response = create_endpoint(expiry_parameter_values['endpoint_name'], expiry_parameter_values['endpoint_config_name'])
                except botocore.exceptions.ClientError as error:
                    print("Error creating endpoint")

            print(error)

def create_endpoint(endpoint_name, endpoint_config_name):
    return sagemaker_client.create_endpoint(
                                        EndpointName=endpoint_name, 
                                        EndpointConfigName=endpoint_config_name)

def handler(event, context):

    # Get expiry
    # expiry_parameter = ssm_client.get_parameter(Name=SSM_ENDPOINT_EXPIRY_PARAMETER)
    # expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])

    # Get a list of endpoint expiry parameters
    response = ssm_client.get_parameters_by_path(
        Path="/sagemaker/endpoint/expiry/",
        Recursive=True)
    result = response["Parameters"]

    
    while "NextToken" in response:
        response = ssm_client.get_parameters_by_path(
            Path="/sagemaker/endpoint/expiry/",
            Recursive=True,
            NextToken=result["NextToken"])
        result.extend(response["Parameters"])

    # Process each endpoint expiry configuration
    for parameter in result:
        print("Processing endpoint")
        # endpoint_name = parameter['Name'].split("/")[-1]
        parameter_values = json.loads(parameter['Value'])
        start_stop_endpoint(parameter_values) 

    # start_stop_endpoint(expiry_parameter_values)


    
