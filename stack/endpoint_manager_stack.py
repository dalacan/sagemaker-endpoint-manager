from aws_cdk import (
    Stack,
    Duration,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets
)

from constructs import Construct

from datetime import datetime, timedelta

import json

class EndpointManagerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, project_prefix, model_name, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create endpoint manager lambdas
        endpoint_name = f"{project_prefix}-{model_name}-Endpoint"

        start_endpoint_handler = _lambda.Function(self, f"StartEndpointHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("api/start_stop_endpoint"),
                handler="app.handler",
                timeout=Duration.seconds(30),
                environment={
                    "SSM_ENDPOINT_EXPIRY_PARAMETER": f"/sagemaker/endpoint/expiry/{endpoint_name}"
                })

        # Add policy to lambda to create endpoint
        start_endpoint_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sagemaker:CreateEndpoint", "sagemaker:DeleteEndpoint", "sagemaker:DescribeEndpoint"],
            resources=[
                "*"
            ],
        ))

        ssm_arn = f"arn:aws:ssm:{self.region}:{self.account}:parameter/sagemaker/endpoint/expiry/*"
        
        # Add SSM read access
        start_endpoint_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ssm:DescribeParameters", "ssm:GetParameter", "ssm:GetParameterHistory", "ssm:GetParameters", "ssm:GetParametersByPath"],
            resources=[
                ssm_arn
            ],
        ))

        start_stop_endpoint_rule = events.Rule(self, 'eventStartStopLambdaRule',
                                           description='Start/Stop Endpoint Lambda Rule',
                                           schedule=events.Schedule.rate(Duration.minutes(1)),
                                           targets=[targets.LambdaFunction(handler=start_endpoint_handler)])
        
        self.update_expiry_handler = _lambda.Function(self, f"UpdateExpiryHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("api/update_expiry"),
                handler="app.handler",
                timeout=Duration.seconds(30),
                environment={
                    "SSM_ENDPOINT_EXPIRY_PARAMETER": f"/sagemaker/endpoint/expiry/{endpoint_name}"
                })

        # Add SSM read/write policy
        self.update_expiry_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ssm:DescribeParameters", "ssm:GetParameter", "ssm:GetParameterHistory", "ssm:GetParameters", "ssm:PutParameter", "ssm:GetParametersByPath"],
            resources=[
                ssm_arn
            ],
        ))