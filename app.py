#!/usr/bin/env python3
import os
from script.sagemaker_uri import *

import aws_cdk as cdk

from stack.api_stack import APIStack
from stack.foundation_model_realtime_stack import FoundationModelRealtimeStack
from stack.foundation_model_async_stack import FoundationModelAsyncStack

from stack.endpoint_manager_stack import EndpointManagerStack

from stack.lambda_stack import LambdaStack

####################################################################################################
# Define configurations
region_name = "us-east-1"
async_inference = False
initial_provision_time_minutes=60
project_prefix = "demo"


# Select an example model endpoint to deploy
# Flan Model example
# model_name="FlanT5"
# MODEL_ID = "huggingface-text2text-flan-t5-xxl"
# INFERENCE_INSTANCE_TYPE = "ml.g5.12xlarge" 
# LAMBDA_SRC = "api/flan"
# API_RESOURCE ="flan"

# Falcon 40B Model example
model_name="Falcon40B"
MODEL_ID = "huggingface-textgeneration-falcon-40b-instruct-bf16"
INFERENCE_INSTANCE_TYPE = "ml.g5.12xlarge"
LAMBDA_SRC = "api/falcon"
API_RESOURCE ="falcon"

MODEL_INFO = get_sagemaker_uris(model_id=MODEL_ID,
                                        instance_type=INFERENCE_INSTANCE_TYPE,
                                        region_name=region_name)

# Define region to deploy stack into
environment = cdk.Environment(region=region_name)
####################################################################################################

app = cdk.App()
fm_stack = FoundationModelRealtimeStack(app, "ModelMeteredStack", 
                                env=environment,
                                project_prefix = project_prefix, 
                                model_name=model_name, 
                                model_info=MODEL_INFO,
                                deploy_enable=False
)

endpoint_manager_stack = EndpointManagerStack(app, "EndpointManagerStack",
                                              env=environment,
                                              project_prefix=project_prefix,
                                              model_name=model_name,
                                              initial_provision_time_minutes=initial_provision_time_minutes,
                                              model_stack=fm_stack
)

# Deploys an async version of the model
fm_async_stack = FoundationModelAsyncStack(app, "ModelAsyncStack",
                                            env=environment,
                                            project_prefix = project_prefix, 
                                            model_name=model_name, 
                                            model_info=MODEL_INFO,
)

# Deploy lambda-sagemaker endpoint integration
lambda_stack = LambdaStack(app, "FlanT5LambdaStack", 
                           env=environment,
                           resource_name=API_RESOURCE,
                           asset_dir=LAMBDA_SRC,
                           endpoint_name=f"{project_prefix}-{model_name}-Endpoint"
)

# Create API gateway to expose both the lambda-endpoint integration and endpoint management
api_stack = APIStack(app, "APIStack", 
                     env=environment,
                     lambda_stack=lambda_stack,
                     endpoint_manager_stack=endpoint_manager_stack
)


app.synth()
