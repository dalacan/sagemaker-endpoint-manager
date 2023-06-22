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

class EndpointManagerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, project_prefix, model_name, initial_provision_time_minutes, model_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create endpoint manager lambdas
        endpoint_name = f"{project_prefix}-{model_name}-Endpoint"

        # Set endpoint expiry
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=initial_provision_time_minutes)

        expiry_ssm = ssm.StringParameter(self, f"{endpoint_name}-expiry", parameter_name=f"{endpoint_name}-expiry", string_value=expiry.strftime("%d-%m-%Y-%H-%M-%S"))
        
        start_endpoint_handler = _lambda.Function(self, f"StartEndpointHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("api/start_stop_endpoint"),
                handler="app.handler",
                timeout=Duration.seconds(30),
                environment={
                    "ENDPOINT_NAME": endpoint_name,
                    "ENDPOINT_CONFIG_NAME": model_stack.endpoint.config.attr_endpoint_config_name
                })

        endpoint_arn = f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/{endpoint_name.lower()}"

        # Add policy to lambda to create endpoint
        start_endpoint_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sagemaker:CreateEndpoint", "sagemaker:DeleteEndpoint", "sagemaker:DescribeEndpoint"],
            resources=[
                "*"
            ],
        ))

        expiry_ssm.grant_read(start_endpoint_handler)

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
                    "ENDPOINT_NAME": endpoint_name
                })
        
        expiry_ssm.grant_read(self.update_expiry_handler)
        expiry_ssm.grant_write(self.update_expiry_handler)
                                                                             
        