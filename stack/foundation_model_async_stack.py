from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_sns as sns,
    aws_s3 as s3
)

from constructs import Construct

from construct.sagemaker_async_endpoint_construct import SageMakerAsyncEndpointConstruct

from datetime import datetime
from stack.util import merge_env

class FoundationModelAsyncStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, project_prefix, model_name, model_info, model_env, **kwargs) -> None:
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

        # Append datetime to model name
        now = datetime.utcnow()
        model_suffix = now.strftime("%d-%m-%Y-%H-%M-%S-%f")[:-3]
        
        # Create sns success and error topic
        success_topic = sns.Topic(self, f"{model_name}-SuccessTopic",
                                    display_name=f"{model_name}-SuccessTopic")
        
        error_topic = sns.Topic(self, f"{model_name}-ErrorTopic",
                                    display_name=f"{model_name}-ErrorTopic")
        
        sns_policy = iam.Policy(self, "sm-deploy-policy-sns",
                                    statements=[iam.PolicyStatement(
                                        effect=iam.Effect.ALLOW,
                                        actions=["sns:Publish"],
                                        resources=[success_topic.topic_arn, error_topic.topic_arn]
                                    )]
        )

        s3_async = s3.Bucket(self, f"{model_name}-S3Async")

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
                            "SAGEMAKER_MODEL_SERVER_WORKERS": "1",
                            "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                            "SAGEMAKER_PROGRAM": "inference.py",
                            "SAGEMAKER_REGION": model_info["region_name"],
                            "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                        }

        environment = merge_env(environment, model_env)

        endpoint = SageMakerAsyncEndpointConstruct(self, "FoundationModelEndpoint",
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
                        deploy_enable = True,

                        success_topic=success_topic.topic_arn,
                        error_topic=error_topic.topic_arn,
                        s3_async_bucket=s3_async.bucket_name,
        )
        endpoint.node.add_dependency(role)
        endpoint.node.add_dependency(sts_policy)
        endpoint.node.add_dependency(logs_policy)
        endpoint.node.add_dependency(ecr_policy)
        