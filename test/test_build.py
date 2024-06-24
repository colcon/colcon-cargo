# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

import asyncio
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace

from colcon_cargo.package_identification.cargo import CargoPackageIdentification  # noqa: E501
from colcon_cargo.task.cargo.build import CargoBuildTask
from colcon_core.event_handler.console_direct import ConsoleDirectEventHandler
from colcon_core.package_descriptor import PackageDescriptor
from colcon_core.subprocess import new_event_loop
from colcon_core.task import TaskContext
import pytest

test_project_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 'rust-sample-package')


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
    assert desc.name == 'rust-sample-app'


@pytest.mark.skipif(
    not shutil.which('cargo'),
    reason='Rust must be installed to run this test')
@pytest.mark.skipif(
    os.name == 'nt' and 'VisualStudioVersion' not in os.environ,
    reason='Must be run from a developer command prompt')
def test_build_package():
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
            assert (install_base / 'bin' / 'rust-sample-app').is_file()
    finally:
        event_loop.close()
