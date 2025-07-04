# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

import asyncio
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import xml.etree.ElementTree as eTree

from colcon_cargo.package_augmentation.cargo import CargoPackageAugmentation
from colcon_cargo.package_discovery.cargo_workspace \
    import CargoWorkspacePackageDiscovery
from colcon_cargo.package_identification.cargo \
    import CargoPackageIdentification
from colcon_cargo.package_identification.cargo_workspace \
    import CargoWorkspaceIdentification
from colcon_cargo.task.cargo.build import CargoBuildTask
from colcon_cargo.task.cargo.test import CargoTestTask
from colcon_core.event_handler.console_direct import ConsoleDirectEventHandler
from colcon_core.package_descriptor import PackageDescriptor
from colcon_core.subprocess import new_event_loop
from colcon_core.task import TaskContext
import pytest

TEST_PACKAGE_NAME = 'rust-sample-package'
PURE_LIBRARY_PACKAGE_NAME = 'rust-pure-library'
WORKSPACE_PACKAGE_NAME = 'rust-workspace'

test_project_path = Path(__file__).parent / TEST_PACKAGE_NAME
pure_library_path = Path(__file__).parent / PURE_LIBRARY_PACKAGE_NAME
workspace_project_path = Path(__file__).parent / WORKSPACE_PACKAGE_NAME


@pytest.fixture(autouse=True)
def monkey_patch_put_event_into_queue(monkeypatch):
    event_handler = ConsoleDirectEventHandler()
    monkeypatch.setattr(
        TaskContext,
        'put_event_into_queue',
        lambda self, event: event_handler((event, 'cargo')),
    )


def test_package_identification():
    cpi = CargoPackageIdentification()
    desc = PackageDescriptor(test_project_path)
    cpi.identify(desc)
    assert desc.type == 'cargo'
    assert desc.name == TEST_PACKAGE_NAME


def test_package_augmentation():
    cpi = CargoPackageIdentification()
    aug = CargoPackageAugmentation()

    desc = PackageDescriptor(pure_library_path)
    cpi.identify(desc)
    aug.augment_package(desc)
    print(desc)
    assert desc.metadata['version'] == '0.1.0'
    assert len(desc.metadata['maintainers']) == 1
    assert desc.metadata['maintainers'][0] == 'Test<test@test.com>'
    assert len(desc.dependencies['build']) == 1
    assert 'either' in desc.dependencies['build']
    assert desc.dependencies['run'] == desc.dependencies['build']

    desc = PackageDescriptor(test_project_path)
    cpi.identify(desc)
    aug.augment_package(desc)
    print(desc)
    assert len(desc.dependencies['build']) == 3
    assert PURE_LIBRARY_PACKAGE_NAME in desc.dependencies['build']
    assert 'windows-sys' in desc.dependencies['build']
    assert 'tempdir' in desc.dependencies['build']
    assert len(desc.dependencies['run']) == 2
    assert PURE_LIBRARY_PACKAGE_NAME in desc.dependencies['run']
    assert 'windows-sys' in desc.dependencies['run']


def test_package_discovery():
    cwi = CargoWorkspaceIdentification()
    cpi = CargoPackageIdentification()
    desc = PackageDescriptor(workspace_project_path)
    cwi.identify(desc)
    assert not desc.type
    assert not desc.name
    cpi.identify(desc)
    assert desc.type == 'cargo'
    assert desc.name == WORKSPACE_PACKAGE_NAME

    cwpd = CargoWorkspacePackageDiscovery()
    descs = cwpd.discover(
        args=SimpleNamespace(),
        identification_extensions={
            cwi.PRIORITY: {'cargo_workspace': cwi},
            cpi.PRIORITY: {'cargo': cpi},
        })

    assert len(descs) == 1
    desc = descs.pop()
    assert desc.type == 'cargo'
    assert desc.name == 'workspace-member'


# Ported from Python 3.13 implementation
# Remove when migrating to Python 3.13 and above
def from_uri(uri):
    """Return a new path from the given 'file' URI."""
    if not uri.startswith('file:'):
        raise ValueError(f"URI does not start with 'file:': {uri!r}")
    path = uri[5:]
    if path[:3] == '///':
        # Remove empty authority
        path = path[2:]
    elif path[:12] == '//localhost/':
        # Remove 'localhost' authority
        path = path[11:]
    if path[:3] == '///' or (path[:1] == '/' and path[2:3] in ':|'):
        # Remove slash before DOS device/UNC path
        path = path[1:]
    if path[1:2] == '|':
        # Replace bar with colon in DOS drive
        path = path[:1] + ':' + path[2:]
    return path


def test_path_dependencies():
    cpi = CargoPackageIdentification()
    aug = CargoPackageAugmentation()
    desc = PackageDescriptor(test_project_path)
    cpi.identify(desc)
    aug.augment_package(desc)
    for dep in desc.dependencies['build']:
        if dep.name == PURE_LIBRARY_PACKAGE_NAME:
            break
    else:
        assert False, f'{PURE_LIBRARY_PACKAGE_NAME} not in build deps'
    assert 'cargo_source' in dep.metadata
    assert dep.metadata['cargo_source'] is not None
    # Path.from_uri was only added in Python 3.13
    assert dep.metadata['cargo_source'].startswith('file://')
    path = from_uri(dep.metadata['cargo_source'])
    # Make sure the dependency path is resolved
    assert Path.is_dir(Path(path))


@pytest.mark.skipif(
    not shutil.which('cargo'),
    reason='Rust must be installed to run this test')
def test_build_and_test_package():
    event_loop = new_event_loop()
    asyncio.set_event_loop(event_loop)

    try:
        cpi = CargoPackageIdentification()
        package = PackageDescriptor(test_project_path)
        cpi.identify(package)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # TODO(luca) Also test clean build and cargo args
            context = TaskContext(pkg=package,
                                  args=SimpleNamespace(
                                      path=str(test_project_path),
                                      build_base=str(tmpdir / 'build'),
                                      install_base=str(tmpdir / 'install'),
                                      clean_build=None,
                                      cargo_args=None,
                                  ),
                                  dependencies={}
                                  )

            task = CargoBuildTask()
            task.set_context(context=context)

            src_base = test_project_path / 'src'

            source_files_before = set(src_base.rglob('*'))
            rc = event_loop.run_until_complete(task.build())
            assert not rc
            source_files_after = set(src_base.rglob('*'))
            assert source_files_before == source_files_after

            # Make sure the binary is compiled
            install_base = Path(task.context.args.install_base)
            app_name = TEST_PACKAGE_NAME
            # Executable in windows have a .exe extension
            if os.name == 'nt':
                app_name += '.exe'
            assert (install_base / 'bin' / app_name).is_file()

            # Now compile tests
            task = CargoTestTask()
            task.set_context(context=context)

            # Expect tests to have failed but return code will still be 0
            # since testing run succeeded
            rc = event_loop.run_until_complete(task.test())
            assert not rc
            build_base = Path(task.context.args.build_base)

            # Make sure the testing files are built
            assert (build_base / 'debug' / 'deps').is_dir()
            assert len(os.listdir(build_base / 'debug' / 'deps')) > 0
            result_file_path = build_base / 'cargo_test.xml'
            assert result_file_path.is_file()
            check_result_file(result_file_path)

    finally:
        event_loop.close()


@pytest.mark.skipif(
    not shutil.which('cargo'),
    reason='Rust must be installed to run this test')
def test_skip_pure_library_package():
    event_loop = new_event_loop()
    asyncio.set_event_loop(event_loop)

    try:
        cpi = CargoPackageIdentification()
        package = PackageDescriptor(pure_library_path)
        cpi.identify(package)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # TODO(luca) Also test clean build and cargo args
            context = TaskContext(pkg=package,
                                  args=SimpleNamespace(
                                      path=str(pure_library_path),
                                      build_base=str(tmpdir / 'build'),
                                      install_base=str(tmpdir / 'install'),
                                      clean_build=None,
                                      cargo_args=None,
                                  ),
                                  dependencies={}
                                  )

            task = CargoBuildTask()
            task.set_context(context=context)

            # Make sure the task succeeds, even though there is no binary
            rc = event_loop.run_until_complete(task.build())
            assert not rc

    finally:
        event_loop.close()


# Check the testing result file, expect cargo test and doc test to fail
# but fmt to succeed
def check_result_file(path):
    tree = eTree.parse(path)
    root = tree.getroot()
    testsuite = root.find('testsuite')
    assert testsuite is not None
    unit_result = testsuite.find("testcase[@name='unit']")
    assert unit_result is not None
    assert unit_result.find('failure') is not None
    fmt_result = testsuite.find("testcase[@name='fmt']")
    assert fmt_result is not None
    assert fmt_result.find('failure') is None


@pytest.mark.skipif(
    not shutil.which('cargo'),
    reason='Rust must be installed to run this test')
def test_workspace_with_package():
    event_loop = new_event_loop()
    asyncio.set_event_loop(event_loop)

    try:
        cpi = CargoPackageIdentification()
        package = PackageDescriptor(workspace_project_path)
        cpi.identify(package)

        assert package.name == WORKSPACE_PACKAGE_NAME

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # TODO(luca) Also test clean build and cargo args
            context = TaskContext(pkg=package,
                                  args=SimpleNamespace(
                                      path=str(workspace_project_path),
                                      build_base=str(tmpdir / 'build'),
                                      install_base=str(tmpdir / 'install'),
                                      clean_build=None,
                                      cargo_args=None,
                                  ),
                                  dependencies={}
                                  )

            task = CargoBuildTask()
            task.set_context(context=context)

            rc = event_loop.run_until_complete(task.build())
            assert not rc

            # Make sure the binary is compiled
            install_base = Path(task.context.args.install_base)
            app_name = package.name
            # Executable in windows have a .exe extension
            if os.name == 'nt':
                app_name += '.exe'
            assert (install_base / 'bin' / app_name).is_file()

            # There should only be a single executable
            # This check is specifically to ensure that other workspace
            # members didn't get installed as well
            assert len(tuple((install_base / 'bin').iterdir())) == 1

    finally:
        event_loop.close()
