"""Deploy the SageMaker Endpoint Manager Stack"""
#!/usr/bin/env python3
import json
import aws_cdk as cdk
from stack.sagemaker_endpoint_manager_stack import SagemakerEndpointManagerStack

# Load model configurations from config file
with open('config/configs.json', encoding='UTF-8') as file:
    configs = json.load(file)

# Define region to deploy stack into
environment = cdk.Environment(region=configs["region_name"])

app = cdk.App()

# Deploy the SageMaker Endpoint Manager Stack
sem_stack = SagemakerEndpointManagerStack(app, "SagemakerEndpointManagerStack",
                                         env=environment,
                                         configs=configs
                                         )

app.synth()
