# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

from colcon_core.logging import colcon_logger
from colcon_core.package_identification \
    import PackageIdentificationExtensionPoint
from colcon_core.plugin_system import satisfies_version
import toml

logger = colcon_logger.getChild(__name__)
WORKSPACE = 'WORKSPACE'


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
        if data == WORKSPACE:
            return
        if not data:
            raise RuntimeError(
                'Failed to extract Rust package information from "%s"'
                % cargo_toml.absolute())

        metadata.type = 'cargo'
        if metadata.name is None:
            metadata.name = data['name']
        metadata.dependencies['build'] |= data['depends']
        metadata.dependencies['run'] |= data['depends']


def extract_data(cargo_toml):
    """
    Extract the project name and dependencies from a Cargo.toml file.

    :param Path cargo_toml: The path of the Cargo.toml file
    :rtype: dict
    """
    content = {}
    try:
        content = toml.load(str(cargo_toml))
    except toml.TomlDecodeError:
        logger.error('Decoding error when processing "%s"'
                     % cargo_toml.absolute())
        return

    if 'workspace' in content.keys():
        return WORKSPACE

    # set the project name - fall back to use the directory name
    data = {}
    toml_name_attr = extract_project_name(content)
    data['name'] = toml_name_attr if toml_name_attr is not None else \
        cargo_toml.parent.name

    depends = extract_dependencies(content)
    # exclude self references
    data['depends'] = set(depends) - {data['name']}

    return data


def extract_project_name(content):
    """
    Extract the Cargo project name from the Cargo.toml file.

    :param str content: The Cargo.toml parsed dictionary
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

    :param str content: The Cargo.toml parsed dictionary
    :returns: The dependencies name
    :rtype: list
    """
    return list(content.get('dependencies', {}).keys())
