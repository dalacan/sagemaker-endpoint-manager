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

        ssm_arn = f"arn:aws:ssm:{self.region}:{self.account}:parameter/sagemaker/endpoint/expiry/*"

        # Create create endpoint lambda
        create_endpoint_handler = self.create_create_endpoint_function()
        
        # Create delete endpoint lambda
        delete_endpoint_handler = self.create_delete_endpoint_function()
        
        # Create a role that will allow event bridge scheduler to invoke the lambda
        event_bridge_role = iam.Role(self, 'eventBridgeRole',
                                    assumed_by=iam.ServicePrincipal('scheduler.amazonaws.com'))

        # Add policy to role to allow event bridge scheduler to invoke the lambda
        event_bridge_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["lambda:InvokeFunction"],
            resources=[
                create_endpoint_handler.function_arn,
                delete_endpoint_handler.function_arn
                ],
        ))

        # Create update expiry lambda
        update_expiry_handler = self.create_update_expiry_function(ssm_arn)

        # Create on update expiry lambda
        self.create_on_update_expiry_function(ssm_arn, create_endpoint_handler, delete_endpoint_handler, event_bridge_role)

        # Create api
        self.create_api(api_stack, update_expiry_handler)

    def create_create_endpoint_function(self):
        # Deploy lambda to create endpoint
        create_endpoint_handler = _lambda.Function(self, f"CreateEndpointHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("functions/create_endpoint"),
                handler="app.handler")

        # Add policy to lambda to create endpoint
        create_endpoint_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sagemaker:CreateEndpoint", "sagemaker:DescribeEndpoint"],
            resources=[
                "*"
                ],
        ))

        return create_endpoint_handler


    def create_delete_endpoint_function(self):
        # Deploy lambda to delete endpoint
        delete_endpoint_handler = _lambda.Function(self, f"DeleteEndpointHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("functions/delete_endpoint"),
                handler="app.handler")

        # Add policy to lambda to delete endpoint
        delete_endpoint_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sagemaker:DeleteEndpoint", "sagemaker:DescribeEndpoint"],
            resources=[
                "*"
                ],
        ))

        return delete_endpoint_handler

    def create_update_expiry_function(self, ssm_arn):
        update_expiry_handler = _lambda.Function(self, f"UpdateExpiryHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("functions/update_expiry"),
                handler="app.handler",
                timeout=Duration.seconds(30)
                    )

        # Add SSM read/write policy
        update_expiry_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ssm:DescribeParameters", "ssm:GetParameter", "ssm:GetParameterHistory", "ssm:GetParameters", "ssm:PutParameter", "ssm:GetParametersByPath"],
            resources=[
                ssm_arn
            ],
        ))

        return update_expiry_handler

    def create_on_update_expiry_function(self, ssm_arn, create_endpoint_handler, delete_endpoint_handler, event_bridge_role):
        on_update_expiry_handler = _lambda.Function(self, f"OnUpdateExpiryHandler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset("functions/on_update_expiry"),
                handler="app.handler",
                environment={
                    "CREATE_ENDPOINT_LAMBDA_ARN": create_endpoint_handler.function_arn,
                    "DELETE_ENDPOINT_LAMBDA_ARN": delete_endpoint_handler.function_arn,
                    "EVENT_BRIDGE_ROLE_ARN": event_bridge_role.role_arn},
                timeout=Duration.seconds(30))

        # Add policy to create endpoint
        on_update_expiry_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sagemaker:CreateEndpoint", "sagemaker:DescribeEndpoint", "sagemaker:DeleteEndpoint"],
            resources=[
                "*"
            ],
        ))

        # Add SSM read/write policy
        on_update_expiry_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ssm:GetParameter"],
            resources=[
                ssm_arn
            ],
        ))

        # Add scheduler policy
        on_update_expiry_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["scheduler:CreateSchedule", "scheduler:GetSchedule", "scheduler:UpdateSchedule", "scheduler:CreateScheduleGroup", "scheduler:DeleteSchedule", "scheduler:ListSchedules"],
            resources=[
                "*"
            ],
        ))

        # Add policy to pass role
        on_update_expiry_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["iam:PassRole"],
            resources=[
                event_bridge_role.role_arn
            ],
            conditions={
                "StringLike": {
                    "iam:PassedToService": [
                        "scheduler.amazonaws.com"
                    ]
                }
            }
        ))

        # Create an event rule to trigger the lambda base on a creation/update to system parameter
        update_expiry_rule = events.Rule(self, 'eventUpdateExpiryLambdaRule',
                                           description='Update Endpoint Expiry Lambda Rule',
                                           event_pattern=events.EventPattern(
                                               source=["aws.ssm"],
                                               detail_type=["Parameter Store Change"],
                                               detail={
                                                "name": [
                                                    {"prefix": "/sagemaker/endpoint/expiry/"}
                                                ]
                                               }
                                           )
        )

        update_expiry_rule.add_target(targets.LambdaFunction(handler=on_update_expiry_handler))


    def create_api(self, api_stack, update_expiry_handler):
        # Add lambda to api gateway
        post_update_expiry_integration = apigateway.LambdaIntegration(update_expiry_handler,
                                                                  request_templates={"application/json": '{ "statusCode": "200" }'})
        # Add lambda to api
        resource = api_stack.api.root.add_resource('endpoint-expiry')
        resource.add_method("POST", post_update_expiry_integration, authorizer=api_stack.api_authorizer)
        resource.add_method("GET", post_update_expiry_integration, authorizer=api_stack.api_authorizer)
