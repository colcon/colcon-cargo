# Copyright 2025 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from colcon_cargo.package_identification.cargo_workspace \
    import CargoWorkspaceIdentification
from colcon_core.package_discovery import PackageDiscoveryExtensionPoint
from colcon_core.package_identification import identify
from colcon_core.package_identification import IgnoreLocationException
from colcon_core.plugin_system import satisfies_version


class CargoWorkspacePackageDiscovery(PackageDiscoveryExtensionPoint):
    """Discover packages which are part of a cargo workspace."""

    # the priority should be very low because we need to discover the
    # workspaces themselves before we can enumerate their sub-packages
    PRIORITY = 10

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageDiscoveryExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.1')

    def has_parameters(self, *, args):  # noqa: D102
        return None

    def discover(self, *, args, identification_extensions):  # noqa: D102
        # Nested workspaces are not currently supported by cargo. If they ever
        # are, this code should be updated to run the whole process again until
        # no additional member package paths are found.

        paths = set()
        for extensions_same_prio in identification_extensions.values():
            for extension in extensions_same_prio.values():
                if isinstance(extension, CargoWorkspaceIdentification):
                    paths.update(extension.workspace_package_paths)
                    extension.workspace_package_paths.clear()

        descs = set()
        for path in paths:
            try:
                result = identify(identification_extensions, path)
            except IgnoreLocationException:
                continue
            if result:
                descs.add(result)
        return descs
