import sagemaker
from sagemaker import script_uris
from sagemaker import image_uris 
from sagemaker import model_uris
from sagemaker.jumpstart.notebook_utils import list_jumpstart_models
from sagemaker import environment_variables
from sagemaker.jumpstart.utils import verify_model_region_and_return_specs
from sagemaker.jumpstart.enums import JumpStartScriptScope
from sagemaker.jumpstart.constants import (
    JUMPSTART_DEFAULT_REGION_NAME,
)
import boto3
from typing import Optional

# session = sagemaker.Session()

def sagemaker_env(model_id, region, model_version="*"):
    extra_env_vars = environment_variables.retrieve_default(
        model_id=model_id,
        model_version=model_version,
        region=region,
        include_aws_sdk_env_vars=False
    )

    return extra_env_vars

def get_sagemaker_uris(model_id,instance_type,region_name):
    
    
    MODEL_VERSION = "*"  # latest
    SCOPE = "inference"

    inference_image_uri = image_uris.retrieve(region=region_name, 
                                          framework=None,
                                          model_id=model_id, 
                                          model_version=MODEL_VERSION, 
                                          image_scope=SCOPE, 
                                          instance_type=instance_type)
    
    inference_model_uri = model_uris.retrieve(
                                          region=region_name,
                                          model_id=model_id, 
                                          model_version=MODEL_VERSION, 
                                          model_scope=SCOPE)
    
    inference_source_uri = script_uris.retrieve(
                                            region=region_name,
                                            model_id=model_id, 
                                            model_version=MODEL_VERSION, 
                                            script_scope=SCOPE)

    model_bucket_name = inference_model_uri.split("/")[2]
    model_bucket_key = "/".join(inference_model_uri.split("/")[3:])
    model_docker_image = inference_image_uri

    return {"model_bucket_name":model_bucket_name, "model_bucket_key": model_bucket_key, \
            "model_docker_image":model_docker_image, "instance_type":instance_type, \
                "inference_source_uri":inference_source_uri, "region_name":region_name}

def get_model_spec(
    model_id: str,
    model_version: str,
    region: Optional[str],
    scope: Optional[str] = None,
):
    if region is None:
        region = JUMPSTART_DEFAULT_REGION_NAME

    # Default to inference scope
    if scope is None:
        scope = JumpStartScriptScope.INFERENCE

    model_specs = verify_model_region_and_return_specs(
            model_id=model_id,
            version=model_version,
            scope=scope,
            region=region
        )

    if model_specs is None:
        return None
    
    return model_specs

def get_model_package_arn(
    model_specs,
    region: Optional[str]):
    if region is None:
        region = JUMPSTART_DEFAULT_REGION_NAME

    if model_specs.hosting_model_package_arns is None:
        return None

    # Return regional arn
    regional_arn = model_specs.hosting_model_package_arns.get(region)

    return regional_arn

def enable_network_isolation(model_specs):
    if model_specs.inference_enable_network_isolation is None:
        return False

    # Return regional arn
    inference_enable_network_isolation = model_specs.inference_enable_network_isolation

    return inference_enable_network_isolation
    