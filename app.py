#!/usr/bin/env python3
import os
from script.sagemaker_uri import *

import aws_cdk as cdk

from stack.api_stack import APIStack
from stack.foundation_model_realtime_stack import FoundationModelRealtimeStack
from stack.foundation_model_async_stack import FoundationModelAsyncStack

from stack.endpoint_manager_stack import EndpointManagerStack

from stack.lambda_stack import LambdaStack

# Define configurations for JM start model to deploy here
region_name = "us-east-1"
async_inference = False


project_prefix = "demo"
model_name="FlanT5"
FLAN_MODEL_ID = "huggingface-text2text-flan-t5-xxl"
FLAN_INFERENCE_INSTANCE_TYPE = "ml.g5.12xlarge" 
FLAN_MODEL_INFO = get_sagemaker_uris(model_id=FLAN_MODEL_ID,
                                        instance_type=FLAN_INFERENCE_INSTANCE_TYPE,
                                        region_name=region_name)

# Define region to deploy stack into
env_USA = cdk.Environment(region=region_name)

app = cdk.App()
fm_stack = FoundationModelRealtimeStack(app, "FlanT5MeteredStack", 
                                env=env_USA,
                                project_prefix = project_prefix, 
                                model_name=model_name, 
                                model_info=FLAN_MODEL_INFO,
                                deploy_enable=False
)

endpoint_manager_stack = EndpointManagerStack(app, "EndpointManagerStack",
                                              env=env_USA,
                                              project_prefix=project_prefix,
                                              model_name=model_name,
                                              initial_provision_time_minutes=60,
                                              model_stack=fm_stack
)

# Deploys an async version of the model
fm_async_stack = FoundationModelAsyncStack(app, "FlanT5AsyncStack",
                                            env=env_USA,
                                            project_prefix = project_prefix, 
                                            model_name=model_name, 
                                            model_info=FLAN_MODEL_INFO,
)

# Deploy lambda-sagemaker endpoint integration
lambda_stack = LambdaStack(app, "FlanT5LambdaStack", 
                           env=env_USA,
                           resource_name="flan",
                           asset_dir="api/flan",
                           endpoint_name=f"{project_prefix}-{model_name}-Endpoint"
)

# Create API gateway to expose both the lambda-endpoint integration and endpoint management
api_stack = APIStack(app, "APIStack", 
                     env=env_USA,
                     lambda_stack=lambda_stack,
                     endpoint_manager_stack=endpoint_manager_stack
)


app.synth()
