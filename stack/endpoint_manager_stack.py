from aws_cdk import (
    NestedStack,
    Duration,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_apigateway as apigateway
)

from constructs import Construct

class EndpointManagerStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, api_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create endpoint manager lambdas
        start_endpoint_handler = _lambda.Function(self, f"StartEndpointHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("functions/start_stop_endpoint"),
                handler="app.handler",
                timeout=Duration.seconds(30))

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
        
        update_expiry_handler = _lambda.Function(self, f"UpdateExpiryHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("functions/update_expiry"),
                handler="app.handler",
                timeout=Duration.seconds(30))

        # Add SSM read/write policy
        update_expiry_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ssm:DescribeParameters", "ssm:GetParameter", "ssm:GetParameterHistory", "ssm:GetParameters", "ssm:PutParameter", "ssm:GetParametersByPath"],
            resources=[
                ssm_arn
            ],
        ))

        # Add lambda to api gateway
        post_update_expiry_integration = apigateway.LambdaIntegration(update_expiry_handler,
                                                                  request_templates={"application/json": '{ "statusCode": "200" }'})
        # Add lambda to api
        resource = api_stack.api.root.add_resource('endpoint-expiry')
        resource.add_method("POST", post_update_expiry_integration, authorizer=api_stack.api_authorizer)
        resource.add_method("GET", post_update_expiry_integration, authorizer=api_stack.api_authorizer)