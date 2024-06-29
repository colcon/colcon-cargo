# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

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
        """
        Initialize the CargoBuildTask.

        This method calls the __init__ method of the parent class TaskExtensionPoint
        and checks the version compatibility.
        """
        super().__init__()
        satisfies_version(TaskExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')

    def add_arguments(self, *, parser):  # noqa: D102
        """
        Add command-line arguments for the CargoBuildTask.

        This method adds arguments to the parser for passing arguments to Cargo
        projects and for cleaning the build directory before the build.

        Args:
            parser: The argument parser to add arguments to.
        """
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
        """
        Build the Cargo package.

        This method builds the Cargo package specified in the context. It sets up
        the necessary environment, prepares the build directory, invokes the build
        command, and creates environment scripts if requested.

        Args:
            additional_hooks: Additional hooks to be executed.
            skip_hook_creation: Whether to skip creating environment hooks.

        Returns:
            An integer return code. 0 indicates success, and a non-zero value indicates failure.
        """
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

        if not skip_hook_creation:
            create_environment_scripts(
                self.context.pkg, args, additional_hooks=additional_hooks)

    # Overridden by colcon-ros-cargo
    def _prepare(self, env, additional_hooks):
        """
        Prepare the build environment.

        This method is intended to be overridden by colcon-ros-cargo.
        It creates an environment hook for the package's PATH.

        Args:
            env: The environment to prepare.
            additional_hooks: Additional hooks to be executed.
        """
        pkg = self.context.pkg
        additional_hooks += create_environment_hook(
            'cargo_{}_path'.format(pkg.name),
            Path(self.context.args.install_base), pkg.name,
            'PATH', 'bin'
        )

    # Overridden by colcon-ros-cargo
    def _build_cmd(self, cargo_args):
        """
        Get the build command for Cargo.

        This method is intended to be overridden by colcon-ros-cargo.
        It returns the command to run 'cargo install' with the provided arguments.

        Args:
            cargo_args: Additional arguments to pass to Cargo.

        Returns:
            A list containing the Cargo build command and its arguments.
        """
        args = self.context.args
        return [
            CARGO_EXECUTABLE, 'install',
            '--force',
            '--quiet',
            '--path', args.path,
            '--root', args.install_base,
        ] + cargo_args
