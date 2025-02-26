# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

from colcon_core.logging import colcon_logger
from colcon_core.package_identification import IgnoreLocationException
from colcon_core.package_identification \
    import PackageIdentificationExtensionPoint
from colcon_core.plugin_system import satisfies_version

try:
    # Python 3.11+
    from tomllib import loads as toml_loads
    from tomllib import TOMLDecodeError
except ImportError:
    try:
        from tomli import loads as toml_loads
        from tomli import TOMLDecodeError
    except ImportError:
        from toml import loads as toml_loads
        from toml import TomlDecodeError as TOMLDecodeError

logger = colcon_logger.getChild(__name__)


class CargoPackageIdentification(PackageIdentificationExtensionPoint):
    """Identify Cargo packages with `Cargo.toml` files."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageIdentificationExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.0')
        self.workspace_package_paths = set()

    def identify(self, metadata):  # noqa: D102
        print(" >>>>>>> CHECKING FOR CARGO PACKAGE")
        if metadata.type is not None and metadata.type != 'cargo':
            return

        cargo_toml = metadata.path / 'Cargo.toml'
        if not cargo_toml.is_file():
            return

        content = read_cargo_toml(cargo_toml)
        ws_members = {
            member
            for pattern in content.get('workspace', {}).get('members', ())
            for member in metadata.path.glob(pattern)
        }
        ws_members.difference_update(
            exclude
            for pattern in content.get('workspace', {}).get('exclude', ())
            for exclude in metadata.path.glob(pattern)
        )
        self.workspace_package_paths.update(ws_members)

        package = content.get('package', {})
        if not package and 'workspace' in content:
            # Let the workspace decide what packages live here
            raise IgnoreLocationException()

        name = package.get('name')
        if not name and not metadata.name:
            raise RuntimeError(
                f"Failed to extract project name from '{cargo_toml}'")

        metadata.type = 'cargo'
        if metadata.name is None:
            metadata.name = name


def read_cargo_toml(cargo_toml):
    """
    Read the contents of a Cargo.toml file.

    :param cargo_toml: Path to a Cargo.toml file to read
    :returns: Dictionary containing the processed content of the Cargo.toml
    :raises ValueError: if the content of Cargo.toml is not valid
    """
    try:
        with cargo_toml.open('rb') as f:
            return toml_loads(f.read().decode())
    except TOMLDecodeError as e:
        raise ValueError(
            f"Failed to parse Cargo.toml file at '{cargo_toml}'") from e
