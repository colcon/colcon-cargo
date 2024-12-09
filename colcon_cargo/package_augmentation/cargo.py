# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from colcon_cargo.package_identification.cargo import read_cargo_toml
from colcon_core.dependency_descriptor import DependencyDescriptor
from colcon_core.package_augmentation \
    import PackageAugmentationExtensionPoint
from colcon_core.plugin_system import satisfies_version


class CargoPackageAugmentation(PackageAugmentationExtensionPoint):
    """Augment cargo packages with information from Cargo.toml files."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageAugmentationExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.0')

    def augment_package(  # noqa: D102
        self, metadata, *, additional_argument_names=None
    ):
        if metadata.type != 'cargo':
            return

        self._augment_package(
            metadata, additional_argument_names=additional_argument_names)

    def _augment_package(
        self, metadata, *, additional_argument_names=None
    ):
        cargo_toml = metadata.path / 'Cargo.toml'
        if not cargo_toml.is_file():
            return

        content = read_cargo_toml(cargo_toml)
        package = content.get('package', {})
        if not package:
            return

        version = package.get('version', '0.0.0')
        if not metadata.metadata.get('version'):
            metadata.metadata['version'] = version

        dependencies = extract_dependencies(content)
        for k, v in dependencies.items():
            metadata.dependencies[k] |= v

        authors = package.get('authors', ())
        if authors:
            metadata.metadata.setdefault('maintainers', [])
            metadata.metadata['maintainers'] += authors


def extract_dependencies(content):
    """
    Get the dependencies of a Cargo package.

    :param content: The dictionary content of the Cargo.tml file
    :returns: The dependencies
    :rtype: dict(string, set(DependencyDescriptor))
    """
    name = content.get('name')
    depends = {
        create_dependency_descriptor(k, v)
        for k, v in content.get('dependencies', {}).items()
        if k != name
    }
    return {
        'build': depends,
        'run': depends,
    }


def create_dependency_descriptor(name, constraints):
    """
    Create a dependency descriptor from a Cargo dependency specification.

    :param name: The name of the dependee
    :param constraints: The dependency constraints, either a string or
      a dict
    :rtype: DependencyDescriptor
    """
    metadata = {
        'origin': 'cargo',
    }
    # TODO: Interpret SemVer constraints and add appropriate constraint
    #       metadata. Handling arbitrary wildcards will be non-trivial.
    return DependencyDescriptor(name, metadata=metadata)
