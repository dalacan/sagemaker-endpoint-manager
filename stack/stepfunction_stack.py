from aws_cdk import (
    Stack,
    NestedStack,
    aws_apigateway as apigateway,
    aws_stepfunctions as sfn,
    aws_iam as iam,
)

from constructs import Construct

class StepFunctionStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, api_stack, step_function_enabled_endpoints, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a step function execution role
        role = iam.Role(self, "StepfunctionExecutionRole", assumed_by=iam.ServicePrincipal("states.amazonaws.com"))

        # Add permission to role to invoke Amazon SageMaker real time endpoint
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sagemaker:InvokeEndpoint"],
                resources=step_function_enabled_endpoints
            )
        )

        # Create an Amazon SageMaker invoke state machine
        sagemaker_invoke_fnc = sfn.StateMachine(self, "SageMakerInvokeStepfunction",
            definition_body=sfn.DefinitionBody.from_file("config/sagemaker-invoke.json"),
            role=role
        )
       
        # Add permission to invoke step function
        api_stack.api_gateway_role.add_to_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["states:StartExecution"],
            resources=[sagemaker_invoke_fnc.state_machine_arn]
            )
        )

        # Add permission to get describe step function execution
        stepfunction_execution_arn = f'arn:aws:states:{self.region}:{self.account}:execution:{sagemaker_invoke_fnc.state_machine_name}:*'

        api_stack.api_gateway_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:DescribeExecution"],
                resources=[stepfunction_execution_arn]
            )
        )

        # Add api integration with step function
        start_execution_resource = api_stack.api.root.add_resource("startexecution")

        # Add apigateway integration with step function using with sagemaker_invoke_fnc state machine arn
        start_execution_integration = apigateway.AwsIntegration(
            service="states",
            integration_http_method="POST",
            action="StartExecution",
            options=apigateway.IntegrationOptions(
                credentials_role=api_stack.api_gateway_role,
                integration_responses=[
                                        apigateway.IntegrationResponse(
                                            status_code="200",
                                        )
                                    ],
                request_templates={"application/json": "{ \"stateMachineArn\": \""+sagemaker_invoke_fnc.state_machine_arn+"\", \"input\": \"$util.escapeJavaScript($input.json('$'))\" }" }
            )
        )

        start_execution_resource.add_method("POST",
                                            start_execution_integration,
                                            authorizer=api_stack.api_authorizer,
                                            method_responses=[
                                                                apigateway.MethodResponse(
                                                                    status_code="200",
                                                                    response_models={
                                                                        "application/json": apigateway.Model.EMPTY_MODEL
                                                                    },
                                                                ),
                                                                apigateway.MethodResponse(
                                                                    status_code="400",
                                                                    response_models={
                                                                        "application/json": apigateway.Model.ERROR_MODEL
                                                                    },
                                                                ),
                                                                apigateway.MethodResponse(
                                                                    status_code="500",
                                                                    response_models={
                                                                        "application/json": apigateway.Model.ERROR_MODEL
                                                                    },
                                                                ),
                                                            ]
        )

        # Add api integration with step function to get step function execution status
        describe_execution_resource = api_stack.api.root.add_resource("describeexecution")

        # Add apigateway integration with step function to get step function execution status
        describe_execution_integration = apigateway.AwsIntegration(
            service="states",
            integration_http_method="POST",
            action="DescribeExecution",
            options=apigateway.IntegrationOptions(
                credentials_role=api_stack.api_gateway_role,
                integration_responses=[
                                        apigateway.IntegrationResponse(
                                            status_code="200",
                                        )
                ]
            )
        )

        describe_execution_resource.add_method("POST",
                                            describe_execution_integration,
                                            authorizer=api_stack.api_authorizer,
                                            method_responses=[
                                                                apigateway.MethodResponse(
                                                                    status_code="200",
                                                                    response_models={
                                                                        "application/json": apigateway.Model.EMPTY_MODEL
                                                                    },
                                                                ),
                                                                apigateway.MethodResponse(
                                                                    status_code="400",
                                                                    response_models={
                                                                        "application/json": apigateway.Model.ERROR_MODEL
                                                                    },
                                                                ),
                                                                apigateway.MethodResponse(
                                                                    status_code="500",
                                                                    response_models={
                                                                        "application/json": apigateway.Model.ERROR_MODEL
                                                                    },
                                                                ),
                                                            ]
        )

            




