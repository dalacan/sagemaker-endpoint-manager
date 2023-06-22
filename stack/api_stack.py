from aws_cdk import (
    # Duration,
    RemovalPolicy,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_dynamodb as dynamodb
)

from constructs import Construct

class APIStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, lambda_stack, endpoint_manager_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB table for authentication
        table_name = "AuthTable"

        auth_db = dynamodb.Table(self, "AuthTable",
                                 table_name=table_name,
                                 partition_key=dynamodb.Attribute(name="token", type=dynamodb.AttributeType.STRING),
                                 removal_policy=RemovalPolicy.DESTROY)

        # Auth handler function
        auth_handler = _lambda.Function(self, "AuthHandler",
                                        code=_lambda.Code.from_asset('api/auth'),
                        runtime=_lambda.Runtime.PYTHON_3_9,
                        handler='auth.handler',
                        environment={
                            "TABLE_NAME": table_name
                            })
        
        auth_db.grant_read_data(auth_handler)
                                        
        self.authorizer = apigateway.RequestAuthorizer(self, "StableDiffusionAuthorizer",
            handler=auth_handler,
            identity_sources=[apigateway.IdentitySource.header("Authorization")]
        )

        self.api = apigateway.RestApi(self, "FoundationModelAPI",
                  rest_api_name="Foundation Model API Service",
                  description="This service serves all the foundation models.")

        self.post_model_integration = apigateway.LambdaIntegration(lambda_stack.app_handler,
                                                                  request_templates={"application/json": '{ "statusCode": "200" }'})
        # Add lambda to api
        resource = self.api.root.add_resource(lambda_stack.resource_name)
        resource.add_method("POST", self.post_model_integration, authorizer=self.authorizer)

        # Update expiry api integration
        self.post_update_expiry_integration = apigateway.LambdaIntegration(endpoint_manager_stack.update_expiry_handler,
                                                                  request_templates={"application/json": '{ "statusCode": "200" }'})
        # Add lambda to api
        resource = self.api.root.add_resource('endpoint-expiry')
        resource.add_method("POST", self.post_update_expiry_integration, authorizer=self.authorizer)
        resource.add_method("GET", self.post_update_expiry_integration, authorizer=self.authorizer)

        # # Lambda
        # app_handler = _lambda.Function(self, "StableDiffusionHandler",
        #         runtime=_lambda.Runtime.PYTHON_3_9,
        #         code=_lambda.Code.from_asset("api/text2text"),
        #         handler="app.handler")

        # get_stable_diffusion_integration = apigateway.LambdaIntegration(app_handler,
        #         request_templates={"application/json": '{ "statusCode": "200" }'})

        # books = self.api.root.add_resource("books")
        # books.add_method("GET")
        # self.api.root.add_method("GET", get_stable_diffusion_integration, authorizer=authorizer)   # GET /

        # Deploy sagemaker model

