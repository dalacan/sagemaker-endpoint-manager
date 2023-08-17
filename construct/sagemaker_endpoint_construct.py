"""SageMaker Endpoint Construct"""
from typing import Optional
from aws_cdk import (
    aws_sagemaker as sagemaker,
    CfnOutput
)
from constructs import Construct

class SageMakerEndpointConstruct(Construct):
    """Class representing a real-time SageMaker Endpoint Construct"""

    def __init__(self, scope: Construct, construct_id: str,
        project_prefix: str,
        role_arn: str,
        model_name: str,
        model_bucket_name: Optional[str],
        model_bucket_key: Optional[str],
        model_docker_image: Optional[str],
        variant_name: str,
        variant_weight: int,
        instance_count: int,
        instance_type: str,
        environment: dict,
        deploy_enable: bool,
        model_package_arn: Optional[str],
        enable_network_isolation: Optional[bool]) -> None:
        super().__init__(scope, construct_id)

        # Do not use a custom named resource for models as these get replaced
        if model_package_arn is not None:
            # Deploy model using model package arn
            container = [
                        sagemaker.CfnModel.ContainerDefinitionProperty(
                                model_package_name=model_package_arn
                            )
                        ]
        else:
            # Deploy model using docker image
            container = [
                        sagemaker.CfnModel.ContainerDefinitionProperty(
                                image= model_docker_image,
                                model_data_url= f"s3://{model_bucket_name}/{model_bucket_key}",
                                environment= environment
                            )
                        ]

        model = sagemaker.CfnModel(self, f"{model_name}-Model",
                execution_role_arn= role_arn,
                containers=container,
                enable_network_isolation=enable_network_isolation
            )

        self.config = sagemaker.CfnEndpointConfig(self, f"{model_name}-Config",
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    model_name= model.attr_model_name,
                    variant_name= variant_name,
                    initial_variant_weight= variant_weight,
                    initial_instance_count= instance_count,
                    instance_type= instance_type
                )
            ]
        )

        self.deploy_enable = deploy_enable
        if deploy_enable:
            self.endpoint = sagemaker.CfnEndpoint(self, f"{model_name}-Endpoint",
                                endpoint_name= f"{project_prefix}-{model_name}-Endpoint",
                                endpoint_config_name= self.config.attr_endpoint_config_name
            )

            CfnOutput(scope=self,id=f"{model_name}EndpointName", value=self.endpoint.endpoint_name)

    @property
    def endpoint_name(self) -> str:
        """Return endpoint name"""
        return self.endpoint.attr_endpoint_name if self.deploy_enable else "not_yet_deployed"
