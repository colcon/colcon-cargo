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

        # Invoke build step
        if CARGO_EXECUTABLE is None:
            raise RuntimeError("Could not find 'cargo' executable")

        cargo_args = args.cargo_args
        if cargo_args is None:
            cargo_args = []
        cmd = self._build_cmd(cargo_args)

        self.progress('build')

        rc = await run(
            self.context, cmd, cwd=self.context.pkg.path, env=env)
        if rc and rc.returncode:
            return rc.returncode

        # colcon-ros-cargo overrides install command to return None.
        # We also need to check if the package has any binaries, because if it
        # has no binaries then cargo install will return an error.
        cmd = self._install_cmd(cargo_args)
        if cmd is not None and await self._has_binaries(env):
            self.progress('install')
            rc = await run(
                self.context, cmd, cwd=self.context.pkg.path, env=env)
            if rc and rc.returncode:
                return rc.returncode

        if not skip_hook_creation:
            create_environment_scripts(
                self.context.pkg, args, additional_hooks=additional_hooks)

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
        return [
            CARGO_EXECUTABLE,
            'build',
            '--quiet',
            '--target-dir', args.build_base,
        ] + cargo_args

    # Overridden by colcon-ros-cargo
    def _install_cmd(self, cargo_args):
        args = self.context.args
        return [
            CARGO_EXECUTABLE,
            'install',
            '--force',
            '--quiet',
            '--locked',
            '--path', '.',
            '--root', args.install_base,
        ] + cargo_args

    # Identify if there are any binaries to install for the current package
    async def _has_binaries(self, env):
        cmd = [
            CARGO_EXECUTABLE,
            'metadata',
            '--no-deps',
            '--format-version', '1',
        ]

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

        metadata = json.loads(rc.stdout)
        for package in metadata.get('packages', {}):
            for target in package.get('targets', {}):
                for crate_type in target.get('crate_types', {}):
                    if crate_type == 'bin':
                        # If any one binary exists in the package then we
                        # should go ahead and run cargo install
                        return True

        # If no binary target exists in the whole package, then skip running
        # cargo install because it would produce an error.
        return False
