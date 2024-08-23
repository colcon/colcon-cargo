# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

import os
from xml.dom import minidom
import xml.etree.ElementTree as eTree

from colcon_cargo.task.cargo import CARGO_EXECUTABLE
from colcon_core.event.test import TestFailure
from colcon_core.logging import colcon_logger
from colcon_core.plugin_system import satisfies_version
from colcon_core.shell import get_command_environment
from colcon_core.task import run
from colcon_core.task import TaskExtensionPoint

logger = colcon_logger.getChild(__name__)


class CargoTestTask(TaskExtensionPoint):
    """Test Cargo packages."""

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

    async def test(self, *, additional_hooks=None):  # noqa: D102
        """
        Runs tests and style checks for the requested package.

        Results are compiled into a single result `cargo_test.xml` file
        with two test results, one for all the tests (cargo test) and one for
        style (`cargo fmt --check`).
        Documentation tests (`cargo test --doc`) are not implemented
        since it is not possible to distinguish between a test that failed
        because of a failing case and one that failed because the crate
        contains no library target.
        """
        pkg = self.context.pkg
        args = self.context.args

        logger.info(
            "Testing Cargo package in '{args.path}'".format_map(locals()))

        assert os.path.exists(args.build_base), \
            'Has this package been built before?'

        test_results_path = os.path.join(args.build_base, 'cargo_test.xml')

        try:
            env = await get_command_environment(
                'test', args.build_base, self.context.dependencies)
        except RuntimeError as e:
            # TODO(luca) log this as error in the test result file
            logger.error(str(e))
            return 1

        if CARGO_EXECUTABLE is None:
            raise RuntimeError("Could not find 'cargo' executable")

        cargo_args = args.cargo_args
        if cargo_args is None:
            cargo_args = []

        # invoke cargo test
        unit_rc = await run(
            self.context,
            self._test_cmd(cargo_args),
            cwd=args.path, env=env, capture_output=True)

        fmt_rc = await run(
            self.context,
            self._fmt_cmd(),
            cwd=args.path, env=env, capture_output=True)

        error_report = self._create_error_report(unit_rc, fmt_rc)
        with open(test_results_path, 'wb') as result_file:
            xmlstr = minidom.parseString(eTree.tostring(error_report))
            xmlstr = xmlstr.toprettyxml(indent='    ', encoding='utf-8')
            result_file.write(xmlstr)

        if unit_rc.returncode or fmt_rc.returncode:
            self.context.put_event_into_queue(TestFailure(pkg.name))
            # the return code should still be 0
        return 0

    def _test_cmd(self, cargo_args):
        args = self.context.args
        return [
            CARGO_EXECUTABLE,
            'test',
            '--quiet',
            '--target-dir',
            args.build_base,
        ] + cargo_args + [
            '--',
            '--color=never',
        ]

    # Ignore cargo args for rustfmt
    def _fmt_cmd(self):
        return [
            CARGO_EXECUTABLE,
            'fmt',
            '--check',
            '--',
            '--color=never',
        ]

    def _create_error_report(self, unit_rc, fmt_rc) -> eTree.Element:
        # TODO(luca) revisit when programmatic output from cargo test is
        # stabilized, for now just have a suite for unit, and fmt tests
        failures = 0
        testsuites = eTree.Element('testsuites')
        # TODO(luca) add time
        testsuite = eTree.SubElement(testsuites,
                                     'testsuite', {'name': 'cargo_test'})
        unit_testcase = eTree.SubElement(testsuite, 'testcase',
                                         {'name': 'unit'})
        if unit_rc.returncode:
            unit_failure = eTree.SubElement(unit_testcase, 'failure',
                                            {'message': 'cargo test failed'})
            unit_failure.text = unit_rc.stdout.decode('utf-8')
            failures += 1
        fmt_testcase = eTree.SubElement(testsuite, 'testcase', {'name': 'fmt'})
        if fmt_rc.returncode:
            fmt_failure = eTree.SubElement(fmt_testcase, 'failure',
                                           {'message': 'cargo fmt failed'})
            fmt_failure.text = fmt_rc.stdout.decode('utf-8')
            failures += 1
        testsuite.attrib['errors'] = str(0)
        testsuite.attrib['failures'] = str(failures)
        testsuite.attrib['skipped'] = str(0)
        testsuite.attrib['tests'] = str(2)
        return testsuites
