# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

from collections import OrderedDict
import json
from pathlib import Path
import shutil
import tarfile

from colcon_cargo.task.cargo import CARGO_EXECUTABLE
from colcon_cargo.task.cargo import get_patch_args
from colcon_core.argument_type import get_cwd_path_resolver
from colcon_core.dependency_descriptor import DependencyDescriptor
from colcon_core.environment import create_environment_scripts
from colcon_core.logging import colcon_logger
from colcon_core.plugin_system import satisfies_version
from colcon_core.shell import create_environment_hook, get_command_environment
from colcon_core.task import create_file
from colcon_core.task import install
from colcon_core.task import run
from colcon_core.task import TaskContext
from colcon_core.task import TaskExtensionPoint

logger = colcon_logger.getChild(__name__)


class _BuildOnlyTaskContext(TaskContext):
    pass


class _PackageOnlyTaskContext(TaskContext):
    pass


class CargoBuildTask(TaskExtensionPoint):
    """Build Cargo packages."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(TaskExtensionPoint.EXTENSION_POINT_VERSION, '^1.1')

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
        parser.add_argument(
            '--additional-crate-paths', type=get_cwd_path_resolver(),
            nargs='*', metavar='REGISTRY_DIR')

    @classmethod
    def create_contexts(cls, *, pkg, args, dependencies):  # noqa: D102
        self_dep = DependencyDescriptor(
            pkg.name + '(crate)',
            metadata={'origin': 'cargo'},
            package_name=pkg.name)

        suffixed_dependencies = OrderedDict(((self_dep, args.install_base),))
        for dep, path in dependencies.items():
            if dep.metadata.get('origin') == 'cargo':
                dep = DependencyDescriptor(
                    dep.name + '(crate)',
                    metadata=dep.metadata,
                    package_name=dep.name)
            suffixed_dependencies[dep] = path

        return {
            self_dep.name: _PackageOnlyTaskContext(
                pkg=pkg, args=args,
                dependencies={}),
            pkg.name: _BuildOnlyTaskContext(
                pkg=pkg, args=args,
                dependencies=suffixed_dependencies),
        }

    async def build(  # noqa: D102
        self, *, additional_hooks=None, skip_hook_creation=False
    ):
        if additional_hooks is None:
            additional_hooks = []

        res = None
        if not isinstance(self.context, (_BuildOnlyTaskContext,)):
            res = await self._package(
                additional_hooks=additional_hooks,
                skip_hook_creation=skip_hook_creation)

        if (
            not res and
            not isinstance(self.context, (_PackageOnlyTaskContext,))
        ):
            res = await self._build(
                additional_hooks=additional_hooks,
                skip_hook_creation=skip_hook_creation)

        return res

    async def _package(
        self, *, additional_hooks=None, skip_hook_creation=False
    ):
        args = self.context.args

        logger.info(
            "Packaging Cargo package in '{args.path}'".format_map(locals()))

        try:
            env = await get_command_environment('package', args.build_base, {})
        except RuntimeError as e:
            logger.error(str(e))
            return 1

        # Clean up the build dir
        build_dir = Path(args.build_base)
        if args.clean_build:
            if build_dir.is_symlink():
                build_dir.unlink()
            elif build_dir.exists():
                shutil.rmtree(build_dir)

        if CARGO_EXECUTABLE is None:
            raise RuntimeError("Could not find 'cargo' executable")

        # Normalize and isolate the manifest
        self._stage = await self._stage_crate(env)

        # Get package metadata
        metadata = await self._get_metadata(env)

        pkg = self.context.pkg
        if self._has_libraries(metadata, pkg.name):
            self.progress('package')
            await self._install_package(
                metadata['packages'][0]['version'], env)

        if not skip_hook_creation:
            create_environment_scripts(
                pkg, args, additional_hooks=additional_hooks)

    async def _build(
        self, *, additional_hooks=None, skip_hook_creation=False
    ):
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

        # Normalize and isolate the manifest
        self._stage = await self._stage_crate(env)

        # Get package metadata
        metadata = await self._get_metadata(env)

        # Patch dependencies
        search_paths = [
            Path(path) for path in args.additional_crate_paths or ()
        ]
        patch_args = get_patch_args(
            self._stage, self.context.dependencies.values(),
            search_paths=search_paths, env=env)

        cargo_args = args.cargo_args
        if cargo_args is None:
            cargo_args = []
        cargo_args = patch_args + cargo_args
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
        build_dir = Path(args.build_base) / '..' / '.cargo_target'
        cmd = [
            CARGO_EXECUTABLE,
            'build',
            '--quiet',
            '--manifest-path', str(self._stage / 'Cargo.toml'),
            '--target-dir', str(build_dir),
        ]
        if not any(
            arg == '--profile' or arg.startswith('--profile=')
            for arg in cargo_args
        ):
            cmd += ['--profile', 'dev']
        return cmd + cargo_args

    # Overridden by colcon-ros-cargo
    def _install_cmd(self, cargo_args):
        args = self.context.args
        build_dir = Path(args.build_base) / '..' / '.cargo_target'
        cmd = [
            CARGO_EXECUTABLE,
            'install',
            '--force',
            '--quiet',
            '--locked',
            '--path', str(self._stage),
            '--root', args.install_base,
            '--target-dir', str(build_dir),
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
            '--manifest-path', str(self._stage / 'Cargo.toml'),
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

    async def _stage_crate(self, env):
        args = self.context.args
        pkg = self.context.pkg
        build_dir = Path(args.build_base) / '..' / '.cargo_target'
        cmd = [
            CARGO_EXECUTABLE,
            'package',
            '--quiet',
            '--package', pkg.name,
            '--target-dir', str(build_dir),
            '--allow-dirty',
            '--exclude-lockfile',
            '--no-metadata',
            '--no-verify',
            '--offline',
        ]
        rc = await run(
            self.context,
            cmd,
            cwd=pkg.path,
            env=env
        )
        if rc is None or rc.returncode != 0:
            raise RuntimeError(
                "Failed to stage the crate using 'cargo package'"
            )

        build_dir = Path(args.build_base)
        crate_version = pkg.metadata['version']
        crate_name = f'{pkg.name}-{crate_version}.crate'
        target_path = build_dir / '..' / '.cargo_target'
        crate_path = target_path / 'package' / crate_name

        with tarfile.open(crate_path, 'r') as crate:
            crate.extractall(build_dir / 'stage')
        stage = build_dir / 'stage' / f'{pkg.name}-{crate_version}'
        (stage / 'Cargo.toml.orig').unlink(missing_ok=True)
        return stage

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

    # Identify if there are any libraries to install for the current package
    @staticmethod
    def _has_libraries(metadata, package_name):
        for package in metadata.get('packages', {}):
            # If the package is part of a cargo workspace, the metadata
            # contains all members. We're only interested in our target
            # package - ignore the other workspace members here.
            if package.get('name') != package_name:
                continue
            for target in package.get('targets', {}):
                if {
                    'lib',
                    'rlib',
                    'proc-macro',
                }.intersection(target.get('crate_types', ())):
                    # If any one binary exists in the package then we
                    # should go ahead and install the extracted crate
                    return True

        # If no library target exists in the whole package, then skip extracted
        # crate installation because it isn't useful.
        return False

    # Determine what files would be part of a packaged crate
    async def _get_crate_contents(self, env):
        pkg = self.context.pkg
        cmd = [
            CARGO_EXECUTABLE,
            'package',
            '--quiet',
            '--package', pkg.name,
            '--allow-dirty',
            '--exclude-lockfile',
            '--no-metadata',
            '--no-verify',
            '--offline',
            '--manifest-path', str(self._stage / 'Cargo.toml'),
            '--list',
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
                "Could not inspect package using 'cargo package'"
            )

        if rc.stdout is None:
            raise RuntimeError(
                "Failed to capture stdout from 'cargo package'"
            )

        contents = set(rc.stdout.decode().splitlines())
        contents.difference_update({
            # Ignore stuff that we wouldn't want to copy
            '',
            None,
            'Cargo.lock',
            'Cargo.toml',
            'Cargo.toml.orig',
            '.cargo_vcs_info.json',
        })
        return contents

    async def _install_package(self, version, env):
        contents = await self._get_crate_contents(env)
        crate_path = Path(
            'share', 'cargo', 'registry', f'{self.context.pkg.name}-{version}')

        for file in contents:
            dst = crate_path / file
            install(self.context.args, file, dst)

        # Use the staged manifest
        install(
            self.context.args,
            self._stage / 'Cargo.toml',
            crate_path / 'Cargo.toml')

        # Cargo "directory sources" require a checksum file to be included in
        # the package metadata (though it need not list all of the files).
        create_file(
            self.context.args,
            crate_path / '.cargo-checksum.json',
            content='{"files":{},"package":""}\n')
