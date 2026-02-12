# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

import os
from pathlib import Path
import shutil

from colcon_core.environment_variable import EnvironmentVariable
from colcon_core.shell import find_installed_packages_in_environment
from pallet_patcher.manifest import get_dependencies
from pallet_patcher.manifest import load_manifest
from pallet_patcher.search import compose
from pallet_patcher.search import get_cargo_arguments

"""Environment variable to override the Cargo executable"""
CARGO_COMMAND_ENVIRONMENT_VARIABLE = EnvironmentVariable(
    'CARGO_COMMAND', 'The full path to the Cargo executable')


def _get_ordered_crate_paths(dependency_paths=None):
    """
    Get all crate search paths for dependencies and parent workspaces.

    :param dependency_paths: Sequence of prefix paths for dependencies.
    :rtype: list
    """
    prefix_paths = list(dependency_paths or ())
    for pkg_path in find_installed_packages_in_environment().values():
        if pkg_path not in prefix_paths:
            prefix_paths.append(pkg_path)
    return [
        Path(prefix) / 'share' / 'cargo' / 'registry'
        for prefix in prefix_paths
    ]


def get_patch_args(
    path, dependency_paths=None, *, search_paths=None, env=None
):
    if env is None:
        env = os.environ

    manifest = load_manifest(path / 'Cargo.toml')
    plain_deps, build_deps, dev_deps = get_dependencies(
        manifest, path)
    dependencies = [
        *plain_deps.items(),
        *build_deps.items(),
        *dev_deps.items(),
    ]

    crate_paths = _get_ordered_crate_paths(dependency_paths)
    crate_paths.extend(search_paths or ())

    composition = compose(dependencies, crate_paths, seeds=[path])
    default_registry = env.get('CARGO_REGISTRY_DEFAULT') or 'crates-io'
    return get_cargo_arguments(composition, default_registry)


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
