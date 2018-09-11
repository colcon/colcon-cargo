# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

import os
import shutil

from colcon_core.environment_variable import EnvironmentVariable

"""Environment variable to override the Cargo executable"""
CARGO_COMMAND_ENVIRONMENT_VARIABLE = EnvironmentVariable(
    'CARGO_COMMAND', 'The full path to the Cargo executable')


def which_executable(environment_variable, executable_name):
    """
    Determine the path of an executable.

    An environment variable can be used to override the location instead of
    relying on searching the PATH.
    :param str environment_variable: The name of the environment variable
    :param str executable_name: The name of the executable
    :rtype: str
    """
    value = os.getenv(environment_variable)
    if value:
        return value
    return shutil.which(executable_name)


CARGO_EXECUTABLE = which_executable(
    CARGO_COMMAND_ENVIRONMENT_VARIABLE.name, 'cargo')
