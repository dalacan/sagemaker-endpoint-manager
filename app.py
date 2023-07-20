#!/usr/bin/env python3
import os
from utils.sagemaker_uri import *
from utils.sagemaker_env import *
import aws_cdk as cdk
from stack.api_stack import APIStack
from stack.foundation_model_stack import FoundationModelStack
from stack.endpoint_manager_stack import EndpointManagerStack
from stack.lambda_stack import LambdaStack
import json

# Load model configurations from config file
with open('config/configs.json') as file:
    configs = json.load(file)

# Define region to deploy stack into
environment = cdk.Environment(region=configs["region_name"])

app = cdk.App()

# Create API gateway to expose both the lambda-endpoint integration and endpoint management
api_stack = APIStack(app, "APIStack", 
                     env=environment,
                     configs=configs
)

# Deploy foundation models configuration and lambda
fm_stack = FoundationModelStack(app, "FoundationModelStack", 
                                env=environment,
                                configs=configs,
                                api_stack=api_stack
)


# Deploy the endpoint manager
endpoint_manager_stack = EndpointManagerStack(app, "EndpointManagerStack",
                                              env=environment,
                                              api_stack = api_stack
)

app.synth()
