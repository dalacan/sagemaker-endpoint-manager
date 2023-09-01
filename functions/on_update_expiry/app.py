import boto3
import botocore

import os
import json
from datetime import datetime, timedelta

ssm_client = boto3.client("ssm")
sagemaker_client = boto3.client('sagemaker')
scheduler_client = boto3.client('scheduler')

delete_endpoint_lambda_arn = os.environ['DELETE_ENDPOINT_LAMBDA_ARN']
event_bridge_role_arn = os.environ['EVENT_BRIDGE_ROLE_ARN']

def get_time_left(expiry):
    expiry = datetime.strptime(expiry, '%d-%m-%Y-%H-%M-%S')
    now = datetime.utcnow()
    time_left = expiry - now

    return time_left

def attempt_create_endpoint(endpoint_name, endpoint_config_name, expiry):
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

def create_update_endpoint_event_bridge_schedule(endpoint_name, expiry):
    expiry = datetime.strptime(expiry, '%d-%m-%Y-%H-%M-%S')

    scheduler_expiry_str = expiry.strftime("%Y-%m-%dT%H:%M:%S")
    print(f'scheduler_expiry_str: {scheduler_expiry_str}')

    schedule_name = f"sem-delete-endpoint-{endpoint_name}"

    # Check if schedule exist
    try:
        response = scheduler_client.get_schedule(
                Name=schedule_name
            )

        print("Existing schedule exist, updating schedule.")

        # Update schedule with new expiry
        scheduler_client.update_schedule(
            Name=schedule_name,
            ScheduleExpression=f"at({scheduler_expiry_str})",
            FlexibleTimeWindow={
                    'Mode': 'OFF'
                },
            Target={
                    'Arn': delete_endpoint_lambda_arn,
                    'Input': json.dumps({'EndpointName': endpoint_name}),
                    'RoleArn': event_bridge_role_arn
                }
        )

    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            print("Schedule does not exist, creating new schedule.")

            # Create an once off eventbridge schedule to invoke a lambda function to delete the endpoint
            scheduler_client.create_schedule(
                # ActionAfterCompletion='DELETE',
                Name=schedule_name,
                ScheduleExpression=f"at({scheduler_expiry_str})",
                State="ENABLED",
                Description=f"Delete endpoint {endpoint_name} at {scheduler_expiry_str}",
                FlexibleTimeWindow={
                    'Mode': 'OFF'
                },
                Target={
                    'Arn': delete_endpoint_lambda_arn,
                    'Input': json.dumps({'EndpointName': endpoint_name}),
                    'RoleArn': event_bridge_role_arn
                }
            )

def delete_expired_endpoint(endpoint_name):
    try:
        print("Checking if endpoint exists")
        # Check endpoint exist
        describe_response = sagemaker_client.describe_endpoint(
            EndpointName=endpoint_name
        )

        print("Endpoint exists, deleting endpoint")
        sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
    except botocore.exceptions.ClientError as error:
        # Endpoint does not exist, create endpoint
        if error.response['Error']['Code'] == 'ValidationException':
            print("Endpoint does not exist, no action required.")
        else:
            print("Error describing endpoint")
            print(error)

def handler(event, context):
    # Get parameters from ssm
    ssm_parameter_name = event['detail']['name']
    expiry_parameter = ssm_client.get_parameter(
            Name=ssm_parameter_name,
            WithDecryption=False)
    expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])
    print(expiry_parameter_values)

    # Check if endpoint is expired
    time_left = get_time_left(expiry_parameter_values['expiry'])

    if time_left.total_seconds() > 0:
        print("Endpoint not expired, attempt to create endpoint if not created")
        attempt_create_endpoint(expiry_parameter_values['endpoint_name'], expiry_parameter_values['endpoint_config_name'], expiry_parameter_values['expiry'])

        create_update_endpoint_event_bridge_schedule(expiry_parameter_values['endpoint_name'], expiry_parameter_values['expiry'])
    else:
        # If endpoint is set to expired date, check if endpoint exists. If it does, delete endpoint
        delete_expired_endpoint(expiry_parameter_values['endpoint_name'])