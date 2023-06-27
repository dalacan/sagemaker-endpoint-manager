from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ssm as ssm
)

from constructs import Construct
from construct.sagemaker_endpoint_construct import SageMakerEndpointConstruct

import json
from datetime import datetime, timedelta
from stack.util import merge_env
class FoundationModelRealtimeStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, project_prefix, model_name, model_info, model_env, initial_provision_time_minutes, deploy_enable, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

        environment = {
                            "MODEL_CACHE_ROOT": "/opt/ml/model",
                            "SAGEMAKER_ENV": "1",
                            "SAGEMAKER_MODEL_SERVER_TIMEOUT": "3600",
                            "SAGEMAKER_MODEL_SERVER_WORKERS": "1",
                            "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                            "SAGEMAKER_PROGRAM": "inference.py",
                            "SAGEMAKER_REGION": model_info["region_name"],
                            "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                        }

        environment = merge_env(environment, model_env)
        
        endpoint = SageMakerEndpointConstruct(self, "FoundationModelEndpoint",
                                    project_prefix = project_prefix,
                                    
                                    role_arn= role.role_arn,

                                    model_name = model_name,
                                    model_bucket_name = model_info["model_bucket_name"],
                                    model_bucket_key = model_info["model_bucket_key"],
                                    model_docker_image = model_info["model_docker_image"],

                                    variant_name = "AllTraffic",
                                    variant_weight = 1,
                                    instance_count = 1,
                                    instance_type = model_info["instance_type"],

                                    environment = environment,
                                    deploy_enable = deploy_enable
        )
        
        endpoint.node.add_dependency(role)
        endpoint.node.add_dependency(sts_policy)
        endpoint.node.add_dependency(logs_policy)
        endpoint.node.add_dependency(ecr_policy)

        endpoint_name = f"{project_prefix}-{model_name}-Endpoint"

        # Set endpoint expiry
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=initial_provision_time_minutes)

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
                                                                             
        