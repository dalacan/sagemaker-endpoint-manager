def merge_env(env, extra_env_vars):
    """Sets env based on default or override, returns envs."""
    if env is None:
        env = {}

    for key, value in extra_env_vars.items():

        if key not in env:
            env[key] = value

    if env == {}:
        env = None

    return env