from aws_cdk import (
    Stack,
    NestedStack,
    Duration,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_sns as sns,
    aws_s3 as s3
)

from constructs import Construct
from construct.sagemaker_endpoint_construct import SageMakerEndpointConstruct
from construct.sagemaker_async_endpoint_construct import SageMakerAsyncEndpointConstruct

import json
from datetime import datetime, timedelta
from stack.util import merge_env

from utils.sagemaker_helper import (
    get_sagemaker_uris,
    sagemaker_env,
    get_model_spec,
    get_model_package_arn,
    enable_network_isolation
)

from stack.stepfunction_stack import StepFunctionStack

class FoundationModelStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, configs, api_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        step_function_enabled_endpoints = []

        # Create policies for model
        role = iam.Role(self, "Gen-AI-SageMaker-Policy", assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"))
        
        sts_policy = iam.Policy(self, "sm-deploy-policy-sts",
                                    statements=[iam.PolicyStatement(
                                        effect=iam.Effect.ALLOW,
                                        actions=[
                                            "sts:AssumeRole"
                                          ],
                                        resources=["*"]
                                    )]
                                )

        logs_policy = iam.Policy(self, "sm-deploy-policy-logs",
                                    statements=[iam.PolicyStatement(
                                        effect=iam.Effect.ALLOW,
                                        actions=[
                                            "cloudwatch:PutMetricData",
                                            "logs:CreateLogStream",
                                            "logs:PutLogEvents",
                                            "logs:CreateLogGroup",
                                            "logs:DescribeLogStreams",
                                            "ecr:GetAuthorizationToken"
                                          ],
                                        resources=["*"]
                                    )]
                                )
        
        ecr_policy = iam.Policy(self, "sm-deploy-policy-ecr",
                                    statements=[iam.PolicyStatement(
                                        effect=iam.Effect.ALLOW,
                                        actions=[
                                            "ecr:*",
                                          ],
                                        resources=["*"]
                                    )]
                                )
                                
        role.attach_inline_policy(sts_policy)
        role.attach_inline_policy(logs_policy)
        role.attach_inline_policy(ecr_policy)

        # Deploy jumpstart models
        for model in configs.get("jumpstart_models", []):
            # Get model info
            model_info = get_sagemaker_uris(model_id=model["model_id"],
                                        instance_type=model["inference_instance_type"],
                                        region_name=configs["region_name"])

            # Get model default environment parameters
            model_env = sagemaker_env(model_id=model["model_id"],
                                    region=configs["region_name"],
                                    model_version="*")

            # Get jumpstart model package arn if available
            model_specs = get_model_spec(
                                model_id=model["model_id"],
                                model_version="*",
                                region=configs["region_name"]
            )

            model_package_arn = get_model_package_arn(
                                model_specs=model_specs,
                                region=configs["region_name"]
            )

            is_network_isolation_enabled = enable_network_isolation(model_specs=model_specs)

            if model["inference_type"] == "realtime":
                # Create real-time endpoint
                # environment = {
                #                     "MODEL_CACHE_ROOT": "/opt/ml/model",
                #                     "SAGEMAKER_ENV": "1",
                #                     "SAGEMAKER_MODEL_SERVER_TIMEOUT": "3600",
                #                     "SAGEMAKER_MODEL_SERVER_WORKERS": "1",
                #                     "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                #                     "SAGEMAKER_PROGRAM": "inference.py",
                #                     "SAGEMAKER_REGION": model_info["region_name"],
                #                     "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                #                 }
                environment = {
                                    "MODEL_CACHE_ROOT": "/opt/ml/model",
                                    "SAGEMAKER_ENV": "1",
                                    "SAGEMAKER_MODEL_SERVER_TIMEOUT": "3600",
                                    "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                                    "SAGEMAKER_PROGRAM": "inference.py",
                                    "SAGEMAKER_REGION": model_info["region_name"],
                                    "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                                }

                environment = merge_env(environment, model_env)
                
                endpoint = SageMakerEndpointConstruct(self, f'FoundationModelEndpoint-{model["name"]}',
                                            project_prefix = configs["project_prefix"],
                                            
                                            role_arn= role.role_arn,

                                            model_name = model["name"],
                                            model_bucket_name = model_info["model_bucket_name"],
                                            model_bucket_key = model_info["model_bucket_key"],
                                            model_docker_image = model_info["model_docker_image"],

                                            variant_name = "AllTraffic",
                                            variant_weight = 1,
                                            instance_count = 1,
                                            instance_type = model_info["instance_type"],

                                            environment = environment,
                                            deploy_enable = False,
                                            model_package_arn=model_package_arn,
                                            enable_network_isolation=is_network_isolation_enabled
                )
                
                endpoint.node.add_dependency(role)
                endpoint.node.add_dependency(sts_policy)
                endpoint.node.add_dependency(logs_policy)
                endpoint.node.add_dependency(ecr_policy)

                endpoint_name = f'{configs["project_prefix"]}-{model["name"]}-Endpoint'

                # Set endpoint expiry
                now = datetime.utcnow()
                expiry = now + timedelta(minutes=model["schedule"]["initial_provision_minutes"])

                expiry_ssm_value = {
                    "expiry": expiry.strftime("%d-%m-%Y-%H-%M-%S"),
                    "endpoint_name": endpoint_name,
                    "endpoint_config_name": endpoint.config.attr_endpoint_config_name
                }

                # Create default SSM parameter to manage endpoint
                expiry_ssm = ssm.StringParameter(self, 
                                                f"{endpoint_name}-expiry", 
                                                parameter_name=f"/sagemaker/endpoint/expiry/{endpoint_name}", 
                                                string_value=json.dumps(expiry_ssm_value))
                
                endpoint_arn = f'arn:aws:sagemaker:{self.region}:{self.account}:endpoint/{endpoint_name.lower()}'
                resource_name = model["integration"]["properties"]["api_resource_name"]

                if model.get("async_api_enabled", False):
                    step_function_enabled_endpoints.append(endpoint_arn)
                
                # Check integration type
                if model["integration"]["type"] == "lambda":
                    # Add lambda/api integration
                    app_handler = _lambda.Function(self, f"{resource_name}Handler",
                    runtime=_lambda.Runtime.PYTHON_3_9,
                    code=_lambda.Code.from_asset(model["integration"]["properties"]["lambda_src"]),
                    handler="app.handler",
                    timeout=Duration.seconds(180),
                    environment={
                        "ENDPOINT_NAME": endpoint_name,
                    })
            
                    # Add sagemaker invoke permissions    
                    app_handler.add_to_role_policy(iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["sagemaker:InvokeEndpoint"],
                        resources=[endpoint_arn],
                    ))

                    post_model_integration = apigateway.LambdaIntegration(app_handler,
                                                                            request_templates={"application/json": '{ "statusCode": "200" }'})
                    # Add lambda to api
                    resource = api_stack.api.root.add_resource(resource_name)
                    resource.add_method("POST", post_model_integration, authorizer=api_stack.api_authorizer)
                elif model["integration"]["type"] == "api":
                    # Add permission to invoke endpoint
                    api_stack.api_gateway_role.add_to_policy(iam.PolicyStatement(
                                                        effect=iam.Effect.ALLOW,
                                                        actions=["sagemaker:InvokeEndpoint"],
                                                        resources=[endpoint_arn],
                                                    )
                                                )
                    
                    # Add api integration/aws integration
                    resource = api_stack.api.root.add_resource(resource_name)
                    post_model_integration = apigateway.AwsIntegration(
                                                        service="runtime.sagemaker",
                                                        integration_http_method="POST",
                                                        path=f"endpoints/{endpoint_name}/invocations",
                                                        options=apigateway.IntegrationOptions(
                                                            request_parameters={
                                                                "integration.request.header.Content-Type": "method.request.header.Content-Type",
                                                                "integration.request.header.Accept": "method.request.header.Accept",
                                                                "integration.request.header.X-Amzn-SageMaker-Custom-Attributes": "method.request.header.X-Amzn-SageMaker-Custom-Attributes"
                                                            },
                                                            credentials_role=api_stack.api_gateway_role,
                                                            integration_responses=[
                                                                apigateway.IntegrationResponse(
                                                                    status_code="200",
                                                                    response_templates={
                                                                        "application/json": "$input.json('$')"
                                                                    },
                                                                ),
                                                                apigateway.IntegrationResponse(
                                                                    status_code="400",
                                                                    selection_pattern="4\d{2}",
                                                                    response_templates={
                                                                        "application/json": '{ "error": $input.path("$.OriginalMessage") }'
                                                                    },
                                                                ),
                                                                apigateway.IntegrationResponse(
                                                                    status_code="500",
                                                                    selection_pattern="5\d{2}",
                                                                    response_templates={
                                                                        "application/json": '{ "error": $input.path("$.OriginalMessage") }'
                                                                    },
                                                                ),
                                                            ],
                                                        ),
                                                    )
                    resource.add_method("POST", 
                                        post_model_integration, 
                                        authorizer=api_stack.api_authorizer,
                                        request_parameters={
                                                                "method.request.header.Content-Type": True,
                                                                "method.request.header.Accept": True,
                                                                "method.request.header.X-Amzn-SageMaker-Custom-Attributes": False
                                                            },
                                                            method_responses=[
                                                                apigateway.MethodResponse(status_code="200"),
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
                    
            elif model["inference_type"] == "async":
                # Create async endpoint

                # Create sns success and error topic
                success_topic = sns.Topic(self, f'{model["name"]}-SuccessTopic',
                                            display_name=f'{model["name"]}-SuccessTopic')
                
                error_topic = sns.Topic(self, f'{model["name"]}-ErrorTopic',
                                            display_name=f'{model["name"]}-ErrorTopic')
                
                sns_policy = iam.Policy(self, "sm-deploy-policy-sns",
                                            statements=[iam.PolicyStatement(
                                                effect=iam.Effect.ALLOW,
                                                actions=["sns:Publish"],
                                                resources=[success_topic.topic_arn, error_topic.topic_arn]
                                            )]
                )

                # Create async output bucket
                s3_async = s3.Bucket(self, f'{model["name"]}-S3Async')

                s3_policy = iam.Policy(self, "sm-deploy-policy-s3",
                                            statements=[iam.PolicyStatement(
                                                effect=iam.Effect.ALLOW,
                                                actions=["s3:*"],
                                                resources=[s3_async.bucket_arn]
                                            )]
                )

                role.attach_inline_policy(sns_policy)
                role.attach_inline_policy(s3_policy)

                environment = {
                                    "MODEL_CACHE_ROOT": "/opt/ml/model",
                                    "SAGEMAKER_ENV": "1",
                                    "SAGEMAKER_MODEL_SERVER_TIMEOUT": "3600",
                                    "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                                    "SAGEMAKER_PROGRAM": "inference.py",
                                    "SAGEMAKER_REGION": model_info["region_name"],
                                    "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                                }

                environment = merge_env(environment, model_env)

                endpoint = SageMakerAsyncEndpointConstruct(self, "FoundationModelEndpoint",
                                project_prefix = configs["project_prefix"],
                                
                                role_arn= role.role_arn,

                                model_name = model["name"],
                                model_bucket_name = model_info["model_bucket_name"],
                                model_bucket_key = model_info["model_bucket_key"],
                                model_docker_image = model_info["model_docker_image"],

                                variant_name = "AllTraffic",
                                variant_weight = 1,
                                instance_count = 1,
                                instance_type = model_info["instance_type"],

                                environment = environment,
                                deploy_enable = True,

                                success_topic=success_topic.topic_arn,
                                error_topic=error_topic.topic_arn,
                                s3_async_bucket=s3_async.bucket_name,
                                model_package_arn=model_package_arn,
                                enable_network_isolation=is_network_isolation_enabled
                )
                endpoint.node.add_dependency(role)
                endpoint.node.add_dependency(sts_policy)
                endpoint.node.add_dependency(logs_policy)
                endpoint.node.add_dependency(ecr_policy)
                                                                             
        stepfunction_stack = StepFunctionStack(self, "StepFunctionStack",
                                       api_stack = api_stack,
                                       step_function_enabled_endpoints=step_function_enabled_endpoints)