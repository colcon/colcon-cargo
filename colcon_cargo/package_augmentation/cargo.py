# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from pathlib import Path

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

        package_name = package.get('name')
        version = package.get('version', '0.0.0')
        if not metadata.metadata.get('version'):
            metadata.metadata['version'] = version

        dependencies = extract_dependencies(
            package_name, content, metadata.path
        )
        for k, v in dependencies.items():
            metadata.dependencies[k] |= v

        for category, spec in content.get('target', {}).items():
            dependencies = extract_dependencies(
                package_name, spec, metadata.path
            )
            for k, v in dependencies.items():
                metadata.dependencies[k] |= v

        authors = package.get('authors', ())
        if authors:
            metadata.metadata.setdefault('maintainers', [])
            metadata.metadata['maintainers'] += authors


def extract_dependencies(package_name, content, path):
    """
    Get the dependencies of a Cargo package.

    :param content: The dictionary content of the Cargo.toml file
    :param path: The directory where the Cargo.toml resides
    :returns: The dependencies
    :rtype: dict(string, set(DependencyDescriptor))
    """

    depends = {
        create_dependency_descriptor(k, v, path)
        for k, v in filter_dependency_list(
            content.get('dependencies', {}).items()
        )
    }
    build_depends = {
        create_dependency_descriptor(k, v, path)
        for k, v in filter_dependency_list(
            content.get('build-dependencies', {}).items()
        )
    }
    dev_depends = {
        create_dependency_descriptor(k, v, path)
        for k, v in filter_dependency_list(
            content.get('dev-dependencies', {}).items(),
            filter_out=package_name,
        )
    }
    return {
        'build': depends | build_depends | dev_depends,
        'run': depends | build_depends,
    }


def filter_dependency_list(dependencies, filter_out=None):
    filtered_dependencies = {}
    for dependency, constraints in dependencies:
        if isinstance(constraints, dict):
            dependency = constraints.get('package', dependency)

        if dependency != filter_out:
            filtered_dependencies[dependency] = constraints

    return filtered_dependencies.items()


def create_dependency_descriptor(dependency_name, constraints, path):
    """
    Create a dependency descriptor from a Cargo dependency specification.

    :param name: The name of the dependee as it is imported
    :param constraints: The dependency constraints, either a string or
      a dict
    :param path: The directory from where relative paths should be
      resolved
    :rtype: DependencyDescriptor
    """
    if isinstance(constraints, dict):
        dep_path = constraints.get('path')
        if dep_path:
            full_dep_path = Path.cwd() / path / dep_path
            source = full_dep_path.absolute().as_uri()
        else:
            source = constraints.get('git') or \
                constraints.get('registry')
    else:
        source = None
    metadata = {
        'origin': 'cargo',
        'cargo_source': source,
    }
    # TODO: Interpret SemVer constraints and add appropriate constraint
    #       metadata. Handling arbitrary wildcards will be non-trivial.
    return DependencyDescriptor(dependency_name, metadata=metadata)
