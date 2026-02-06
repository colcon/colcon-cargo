# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

import json
from pathlib import Path
import shutil

from colcon_cargo.task.cargo import CARGO_EXECUTABLE
from colcon_core.environment import create_environment_scripts
from colcon_core.logging import colcon_logger
from colcon_core.plugin_system import satisfies_version
from colcon_core.shell import create_environment_hook, get_command_environment
from colcon_core.task import run
from colcon_core.task import TaskExtensionPoint

from pallet_patcher.command import load_and_compose
from pallet_patcher.search import get_cargo_arguments

logger = colcon_logger.getChild(__name__)


class CargoBuildTask(TaskExtensionPoint):
    """Build Cargo packages."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(TaskExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')

    def add_arguments(self, *, parser):  # noqa: D102
        parser.add_argument(
            '--cargo-args',
            nargs='*', metavar='*', type=str.lstrip,
            help='Pass arguments to Cargo projects. '
            'Arguments matching other options must be prefixed by a space,\n'
            'e.g. --cargo-args " --help"')
        parser.add_argument(
            '--clean-build',
            action='store_true',
            help='Remove old build dir before the build.')

    async def build(  # noqa: D102
        self, *, additional_hooks=None, skip_hook_creation=False
    ):
        if additional_hooks is None:
            additional_hooks = []
        args = self.context.args

        logger.info(
            "Building Cargo package in '{args.path}'".format_map(locals()))

        try:
            env = await get_command_environment(
                'build', args.build_base, self.context.dependencies)
        except RuntimeError as e:
            logger.error(str(e))
            return 1

        self.progress('prepare')
        rc = self._prepare(env, additional_hooks)
        if rc:
            return rc

        # Clean up the build dir
        build_dir = Path(args.build_base)
        if args.clean_build:
            if build_dir.is_symlink():
                build_dir.unlink()
            elif build_dir.exists():
                shutil.rmtree(build_dir)

        if CARGO_EXECUTABLE is None:
            raise RuntimeError("Could not find 'cargo' executable")

        # Get package metadata
        metadata = await self._get_metadata(env)

        ###### Run pallet-patcher to fetch anything available in colcon's workspace
        ###### or in our system dependencies:
        base_path = Path(args.path)

        # TO-DO: How I get this to be the path where colcon is being run? workspace root
        if "/deps" in str(base_path.parent):
            ws_crates_paths = [base_path.parent.parent / Path("deps")]
        else:
            ws_crates_paths = [base_path.parent / Path("deps")]

        system_crates_paths = [Path("/usr/share/cargo/registry/")]
        manifest_path = base_path / Path("Cargo.toml")
        logger.info("Searching for local crates in '{ws_crates_paths}'".format_map(locals()))
        logger.info("Searching for system crates in '{system_crates_paths}'".format_map(locals()))
        logger.info("Searching for metadata in '{manifest_path}'".format_map(locals()))
        composition = load_and_compose(manifest_path, ws_crates_paths, system_crates_paths)
        crates_available_locally = get_cargo_arguments(composition)
        logger.info("Extra crates:" + str(crates_available_locally))

        cargo_args = args.cargo_args
        if cargo_args is None:
            cargo_args = [] + crates_available_locally
        # Invoke build step
        cmd = self._build_cmd(cargo_args)

        self.progress('build')

        pkg = self.context.pkg
        rc = await run(
            self.context, cmd, cwd=pkg.path, env=env)
        if rc and rc.returncode:
            return rc.returncode

        # colcon-ros-cargo overrides install command to return None.
        # We also need to check if the package has any binaries, because if it
        # has no binaries then cargo install will return an error.
        cmd = self._install_cmd(cargo_args)
        if cmd is not None and self._has_binaries(metadata, pkg.name):
            self.progress('install')
            rc = await run(
                self.context, cmd, cwd=pkg.path, env=env)
            if rc and rc.returncode:
                return rc.returncode

        if not skip_hook_creation:
            create_environment_scripts(
                pkg, args, additional_hooks=additional_hooks)

    # Overridden by colcon-ros-cargo
    def _prepare(self, env, additional_hooks):
        pkg = self.context.pkg
        additional_hooks += create_environment_hook(
            'cargo_{}_path'.format(pkg.name),
            Path(self.context.args.install_base), pkg.name,
            'PATH', 'bin'
        )

    # Overridden by colcon-ros-cargo
    def _build_cmd(self, cargo_args):
        args = self.context.args
        pkg = self.context.pkg
        cmd = [
            CARGO_EXECUTABLE,
            'build',
            '--quiet',
            '--package', pkg.name,
            '--target-dir', args.build_base,
        ]
        if not any(
            arg == '--profile' or arg.startswith('--profile=')
            for arg in cargo_args
        ):
            cmd += ['--profile', 'dev']
        logger.info(f"Build command: {cmd} and arguments: {cargo_args}")
        return cmd + cargo_args

    # Overridden by colcon-ros-cargo
    def _install_cmd(self, cargo_args):
        args = self.context.args
        cmd = [
            CARGO_EXECUTABLE,
            'install',
            '--force',
            '--quiet',
            '--locked',
            '--path', '.',
            '--root', args.install_base,
            '--target-dir', args.build_base,
            '--no-track',
        ]
        if not any(
            arg == '--profile' or arg.startswith('--profile=')
            for arg in cargo_args
        ):
            cmd += ['--profile', 'dev']
        return cmd + cargo_args

    async def _get_metadata(self, env):
        cmd = [
            CARGO_EXECUTABLE,
            'metadata',
            '--no-deps',
            '--format-version', '1',
        ]

        # TODO: The reported target_directory is wrong. Does it matter here?
        #       We could maybe override it with --config

        rc = await run(
            self.context,
            cmd,
            cwd=self.context.pkg.path,
            capture_output=True,
            env=env
        )
        if rc is None or rc.returncode != 0:
            raise RuntimeError(
                "Could not inspect package using 'cargo metadata'"
            )

        if rc.stdout is None:
            raise RuntimeError(
                "Failed to capture stdout from 'cargo metadata'"
            )

        return json.loads(rc.stdout)

    # Identify if there are any binaries to install for the current package
    @staticmethod
    def _has_binaries(metadata, package_name):
        for package in metadata.get('packages', {}):
            # If the package is part of a cargo workspace, the metadata
            # contains all members. We're only interested in our target
            # package - ignore the other workspace members here.
            if package.get('name') != package_name:
                continue
            for target in package.get('targets', {}):
                for kind in target.get('kind', {}):
                    if kind == 'bin':
                        # If any one binary exists in the package then we
                        # should go ahead and run cargo install
                        return True

        # If no binary target exists in the whole package, then skip running
        # cargo install because it would produce an error.
        return False
