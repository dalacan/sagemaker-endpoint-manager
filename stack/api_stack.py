from aws_cdk import (
    RemovalPolicy,
    NestedStack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_dynamodb as dynamodb,
    aws_iam as iam
)

from constructs import Construct

class APIStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, configs, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB table for authentication
        table_name = configs.get("ddb_auth_table_name", "AuthTable")

        auth_db = dynamodb.Table(self, "AuthTable",
                                 table_name=table_name,
                                 partition_key=dynamodb.Attribute(name="token", type=dynamodb.AttributeType.STRING),
                                 removal_policy=RemovalPolicy.DESTROY)

        # Auth handler function
        auth_handler = _lambda.Function(self, "AuthHandler",
                                        code=_lambda.Code.from_asset('functions/auth'),
                        runtime=_lambda.Runtime.PYTHON_3_9,
                        handler='auth.handler',
                        environment={
                            "TABLE_NAME": table_name
                            })
        
        auth_db.grant_read_data(auth_handler)
                                        
        self.api_authorizer = apigateway.RequestAuthorizer(self, "APIAuthorizer",
            handler=auth_handler,
            identity_sources=[apigateway.IdentitySource.header("Authorization")]
        )

        self.api = apigateway.RestApi(self, "FoundationModelAPI",
                  rest_api_name="Foundation Model API Service",
                  description="This service serves all the foundation models.")

        self.api_gateway_role = iam.Role(
            self,
            "ApiGatewayRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
