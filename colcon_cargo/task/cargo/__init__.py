# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

from typing import Optional

import os
import shutil

from colcon_core.environment_variable import EnvironmentVariable

# Environment variable to override the Cargo executable
CARGO_COMMAND_ENVIRONMENT_VARIABLE = EnvironmentVariable(
    'CARGO_COMMAND', 'The full path to the Cargo executable')


def which_executable(environment_variable: str, executable_name: str) \
        -> Optional[str]:
    """
    Determine the path of an executable.

    An environment variable can be used to override the location instead of
    relying on searching the PATH.

    :param environment_variable: The name of the environment variable
    :param executable_name: The name of the executable, or None if that's not
                            found
    """
    if environment_variable in os.environ:
        return os.environ[environment_variable]

    which = shutil.which(executable_name)
    if which:
        return which


CARGO_EXECUTABLE = which_executable(
    CARGO_COMMAND_ENVIRONMENT_VARIABLE.name, 'cargo')
