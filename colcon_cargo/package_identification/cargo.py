# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

import toml

from colcon_core.package_identification \
    import PackageIdentificationExtensionPoint
from colcon_core.plugin_system import satisfies_version


class CargoPackageIdentification(PackageIdentificationExtensionPoint):
    """Identify Cargo packages with `Cargo.toml` files."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageIdentificationExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.0')

    def identify(self, metadata):  # noqa: D102
        if metadata.type is not None and metadata.type != 'cargo':
            return

        cargo_toml = metadata.path / 'Cargo.toml'
        if not cargo_toml.is_file():
            return

        data = extract_data(cargo_toml)
        if not data['name'] and not metadata.name:
            raise RuntimeError(
                "Failed to extract project name from '%s'" % cargo_toml)

        metadata.type = 'cargo'
        if metadata.name is None:
            metadata.name = data['name']
        metadata.dependencies['build'] |= data['depends']
        metadata.dependencies['run'] |= data['depends']


def extract_data(cargo_toml):
    """
    Extract the project name and dependencies from a Cargo.toml file.

    :param Path corgo_toml: The path of the Cargo.toml file
    :rtype: dict
    """
    content = {}

    try:
        content = toml.load(str(cargo_toml))
        data = {}
        data['name'] = extract_project_name(content)
    except toml.TomlDecodeError:
        pass

    # fall back to use the directory name
    if data['name'] is None:
        data['name'] = cargo_toml.parent.name

    depends = extract_dependencies(content)
    # exclude self references
    data['depends'] = set(depends) - {data['name']}

    return data


def extract_project_name(content):
    """
    Extract the Cargo project name from the Cargo.toml file.

    :param str content: The Cargo.toml parsed dictionnary
    :returns: The project name, otherwise None
    :rtype: str
    """
    try:
        return content['package']['name']
    except KeyError:
        return None


def extract_dependencies(content):
    """
    Extract the dependencies from the Cargo.toml file.

    :param str content: The Cargo.toml parsed dictionnary
    :returns: The dependencies name
    :rtype: list
    """
    return list(content['dependencies'].keys())
