from sagemaker import environment_variables

def sagemaker_env(model_id, region, model_version="*"):
    extra_env_vars = environment_variables.retrieve_default(
        model_id=model_id,
        model_version=model_version,
        region=region,
        include_aws_sdk_env_vars=False
    )

    return extra_env_vars