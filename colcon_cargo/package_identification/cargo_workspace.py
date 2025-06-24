# Copyright 2025 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from colcon_cargo.package_identification.cargo import read_cargo_toml
from colcon_core.package_identification import IgnoreLocationException
from colcon_core.package_identification \
    import PackageIdentificationExtensionPoint
from colcon_core.plugin_system import satisfies_version


class CargoWorkspaceIdentification(PackageIdentificationExtensionPoint):
    """
    Identify Cargo workspaces with `Cargo.toml` files.

    This extension does not actually identify any packages per se, but is a
    necessary component for CargoWorkspacePackageDiscovery to function.
    """

    # This
    PRIORITY = 990

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageIdentificationExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.0')
        self.workspace_package_paths = set()

    def identify(self, metadata):  # noqa: D102
        if metadata.type is not None and metadata.type != 'cargo':
            return

        cargo_toml = metadata.path / 'Cargo.toml'
        if not cargo_toml.is_file():
            return

        content = read_cargo_toml(cargo_toml)
        if 'workspace' not in content:
            return

        ws_members = {
            member
            for pattern in content['workspace'].get('members', ())
            for member in metadata.path.glob(pattern)
        }
        ws_members.difference_update(
            exclude
            for pattern in content['workspace'].get('exclude', ())
            for exclude in metadata.path.glob(pattern)
        )
        self.workspace_package_paths.update(ws_members)

        if 'package' not in content:
            # Prevent any further attempts to discover packages in this
            # directory and let the workspace dictate where to look for
            # packages later on
            raise IgnoreLocationException()
