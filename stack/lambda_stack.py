from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam
)

from constructs import Construct

class LambdaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, resource_name, asset_dir, model_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create lambda
        self.app_handler = _lambda.Function(self, f"{resource_name}Handler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                code=_lambda.Code.from_asset(asset_dir),
                handler="app.handler",
                timeout=Duration.seconds(180),
                environment={
                    "ENDPOINT_NAME": model_stack.endpoint.endpoint_name,
                })
        
        # print(model_stack.endpoint.endpoint.__dir__())

        # print(model_stack.endpoint.endpoint.ref)

        # print(model_stack.endpoint.endpoint.get_att('EndpointArn'))
        self.app_handler.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sagemaker:InvokeEndpoint"],
            resources=[
                model_stack.endpoint.endpoint.ref
            ],
        ))

       
        
        self.resource_name = resource_name

