import boto3
import botocore

import os
import json
from datetime import datetime, timedelta

ssm_client = boto3.client("ssm")
sagemaker_client = boto3.client('sagemaker')
scheduler_client = boto3.client('scheduler')

create_endpoint_lambda_arn = os.environ['CREATE_ENDPOINT_LAMBDA_ARN']
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
    # print(f'scheduler_expiry_str: {scheduler_expiry_str}')

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

def create_scheduler_group(scheduler_group_name):
    # Create an event bridge scheduler group
    scheduler_group_name = scheduler_group_name
    try:
        response = scheduler_client.create_schedule_group(
            Name=scheduler_group_name
        )
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'ConflictException':
            print("Scheduler group already exists, no action required.")
        else:
            print("Error creating scheduler group")
            print(error)
            return

def generate_cron_expression(time, days):
    time_hh = time.split(':')[0]
    time_mm = time.split(':')[1]

    cron_expression = f"{time_mm} {time_hh} ? * {','.join(days)} *"

    return cron_expression

def generate_one_time_schedule(date, time):
    date_time_obj = datetime.strptime(f'{date} {time}', '%d/%m/%Y %H:%M')

    one_time_schedule = f'at({date_time_obj.strftime("%Y-%m-%dT%H:%M:%S")})'

    return one_time_schedule


def create_endpoint_schedule(endpoint_name, endpoint_config_name, schedules):
    scheduler_group_name = f"sem-endpoint-group-{endpoint_name}"
    # Create scheduler group (if not exists)
    create_scheduler_group(scheduler_group_name)

    # Get a list of event bridge scheduler rules in group
    try:
        event_bridge_schedules_response = scheduler_client.list_schedules(
            GroupName=scheduler_group_name
        )

        print(f'Found {len(event_bridge_schedules_response["Schedules"])} event bridge scheduler rules in group')
        # Delete all event bridge scheduler rules in group
        for schedule in event_bridge_schedules_response['Schedules']:
            print(f'Delete schedule {schedule["Name"]}')
            scheduler_client.delete_schedule(
                Name=schedule['Name'],
                GroupName=scheduler_group_name
            )
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            print("No event bridge scheduler rules exist, no action required.")
        else:
            print("Error listing event bridge schedules")
            print(error)
            return
    
    print("Creating schedules")
    for schedule in schedules:
        start_endpoint_schedule_name = f"sem-start-endpoint-{endpoint_name}-{schedule['name'].lower()}"
        stop_endpoint_schedule_name = f"sem-stop-endpoint-{endpoint_name}-{schedule['name'].lower()}"

        # Default timezone to UTC
        timezone = 'UTC'
        if 'timezone' in schedule:
            timezone = schedule['timezone']

        if 'days' in schedule:
            print("Day schedule")
            start_cron_expression = generate_cron_expression(schedule['start_time'], schedule['days'])
            stop_cron_expression = generate_cron_expression(schedule['stop_time'], schedule['days'])

            # Create a rule to start endpoint
            scheduler_client.create_schedule(
                # ActionAfterCompletion='DELETE',
                Name=start_endpoint_schedule_name,
                GroupName=scheduler_group_name,
                ScheduleExpression=f"cron({start_cron_expression})",
                State="ENABLED",
                Description=f"Start endpoint {endpoint_name}",
                FlexibleTimeWindow={
                    'Mode': 'OFF'
                },
                Target={
                    'Arn': create_endpoint_lambda_arn,
                    'Input': json.dumps(
                        {
                            'EndpointName': endpoint_name,
                            'EndpointConfigName': endpoint_config_name
                        }),
                    'RoleArn': event_bridge_role_arn
                },
                ScheduleExpressionTimezone=timezone
            )

            # Create a rule to delete endpoint
            scheduler_client.create_schedule(
                # ActionAfterCompletion='DELETE',
                Name=stop_endpoint_schedule_name,
                GroupName=scheduler_group_name,
                ScheduleExpression=f"cron({stop_cron_expression})",
                State="ENABLED",
                Description=f"Stop endpoint {endpoint_name}",
                FlexibleTimeWindow={
                    'Mode': 'OFF'
                },
                Target={
                    'Arn': delete_endpoint_lambda_arn,
                    'Input': json.dumps({'EndpointName': endpoint_name}),
                    'RoleArn': event_bridge_role_arn
                },
                ScheduleExpressionTimezone=timezone
            )
        elif 'date' in schedule:
            print("Date schedule")

            if 'start_time' in schedule:
                print("Creating start schedule")
                # Create rule to start endpoint
                scheduler_client.create_schedule(
                    # ActionAfterCompletion='DELETE',
                    Name=start_endpoint_schedule_name,
                    GroupName=scheduler_group_name,
                    ScheduleExpression=generate_one_time_schedule(schedule['date'], schedule['start_time']),
                    State="ENABLED",
                    Description=f"Create endpoint {endpoint_name}",
                    FlexibleTimeWindow={
                        'Mode': 'OFF'
                    },
                    Target={
                        'Arn': create_endpoint_lambda_arn,
                        'Input': json.dumps(
                        {
                            'EndpointName': endpoint_name,
                            'EndpointConfigName': endpoint_config_name
                        }),
                        'RoleArn': event_bridge_role_arn
                    },
                    ScheduleExpressionTimezone=timezone
                )

            if 'stop_time' in schedule:
                print("Creating stop schedule")
                # Create rule to stop endpoint
                scheduler_client.create_schedule(
                    # ActionAfterCompletion='DELETE',
                    Name=stop_endpoint_schedule_name,
                    GroupName=scheduler_group_name,
                    ScheduleExpression=generate_one_time_schedule(schedule['date'], schedule['stop_time']),
                    State="ENABLED",
                    Description=f"Delete endpoint {endpoint_name}",
                    FlexibleTimeWindow={
                        'Mode': 'OFF'
                    },
                    Target={
                        'Arn': delete_endpoint_lambda_arn,
                        'Input': json.dumps({'EndpointName': endpoint_name}),
                        'RoleArn': event_bridge_role_arn
                    },
                    ScheduleExpressionTimezone=timezone
                )

def handler(event, context):
    # Get parameters from ssm
    ssm_parameter_name = event['detail']['name']
    expiry_parameter = ssm_client.get_parameter(
            Name=ssm_parameter_name,
            WithDecryption=False)
    expiry_parameter_values = json.loads(expiry_parameter['Parameter']['Value'])

    if 'expiry' in expiry_parameter_values:
        # Check if endpoint is expired
        time_left = get_time_left(expiry_parameter_values['expiry'])

        if time_left.total_seconds() > 0:
            print("Endpoint not expired, attempt to create endpoint if not created")
            attempt_create_endpoint(expiry_parameter_values['endpoint_name'], expiry_parameter_values['endpoint_config_name'], expiry_parameter_values['expiry'])

            create_update_endpoint_event_bridge_schedule(expiry_parameter_values['endpoint_name'], expiry_parameter_values['expiry'])
        else:
            # If endpoint is set to expired date, check if endpoint exists. If it does, delete endpoint
            delete_expired_endpoint(expiry_parameter_values['endpoint_name'])

    if 'schedule' in expiry_parameter_values:
        print("Creating schedule")
        create_endpoint_schedule(expiry_parameter_values['endpoint_name'], expiry_parameter_values['endpoint_config_name'], expiry_parameter_values['schedule'])