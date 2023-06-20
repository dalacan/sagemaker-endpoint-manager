#!/usr/bin/env python3
import os
from script.sagemaker_uri import *

import aws_cdk as cdk

from stack.api_stack import APIStack
from stack.foundation_model_stack import FoundationModelStack
from stack.lambda_stack import LambdaStack

# Define configurations for JM start model to deploy here
region_name = "us-east-1"
FLAN_MODEL_ID = "huggingface-text2text-flan-t5-xxl"
FLAN_INFERENCE_INSTANCE_TYPE = "ml.g5.12xlarge" 
FLAN_MODEL_INFO = get_sagemaker_uris(model_id=FLAN_MODEL_ID,
                                        instance_type=FLAN_INFERENCE_INSTANCE_TYPE,
                                        region_name=region_name)

# Define region to deploy stack into
env_USA = cdk.Environment(region=region_name)

app = cdk.App()
fm_stack = FoundationModelStack(app, "FlanT5Stack", 
                                env=env_USA,
                                project_prefix = "FlanT5", 
                                model_name="FlanT5", 
                                model_info=FLAN_MODEL_INFO,
                                async_inference=False
)

lambda_stack = LambdaStack(app, "FlanT5LambdaStack", 
                           env=env_USA,
                           resource_name="FLAN",
                           asset_dir="api/flan", 
                           model_stack=fm_stack
)

# Create API gateway
api_stack = APIStack(app, "APIStack", 
                     env=env_USA,
                     lambda_stack=lambda_stack
)


app.synth()
