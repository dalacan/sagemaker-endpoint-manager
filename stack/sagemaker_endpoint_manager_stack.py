from aws_cdk import (
    Stack,
    CfnOutput
)

from constructs import Construct

from stack.api_stack import APIStack
from stack.foundation_model_stack import FoundationModelStack
from stack.endpoint_manager_stack import EndpointManagerStack
from stack.stepfunction_stack import StepFunctionStack

class SagemakerEndpointManagerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, configs, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Deploy api stack
        api_stack = APIStack(self, "APIStack", 
                    configs=configs
        )

        # Deploy endpoint manager stack
        endpoint_manager_stack = EndpointManagerStack(self, "EndpointManagerStack", 
                    api_stack = api_stack
        )

        # Deploy model stack
        fm_stack = FoundationModelStack(self, "ModelStack", 
                                configs=configs,
                                api_stack=api_stack
        )

        CfnOutput(self, "APIURL",
            value=f"https://{api_stack.api.rest_api_id}.execute-api.{self.region}.amazonaws.com/prod"
        )