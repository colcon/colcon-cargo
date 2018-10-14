# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

import os

from colcon_cargo.task.cargo import CARGO_EXECUTABLE
from colcon_core.event.test import TestFailure
from colcon_core.logging import colcon_logger
from colcon_core.plugin_system import satisfies_version
from colcon_core.shell import get_command_environment
from colcon_core.task import check_call
from colcon_core.task import TaskExtensionPoint

from colcon_core.event.command import Command
from colcon_core.event.command import CommandEnded
from colcon_core.event.output import StderrLine
from colcon_core.event.output import StdoutLine
from colcon_core.subprocess import run
from xml.etree.ElementTree import Element, SubElement, ElementTree
import json

logger = colcon_logger.getChild(__name__)


class CargoTestTask(TaskExtensionPoint):
    """Test Cargo packages."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(TaskExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')

    def add_arguments(self, *, parser):  # noqa: D102
        pass

    async def test(self, *, additional_hooks=None):  # noqa: D102
        pkg = self.context.pkg
        args = self.context.args

        logger.info(
            "Testing Cargo package in '{args.path}'".format_map(locals()))

        assert os.path.exists(args.build_base)

        test_results_path = os.path.join(args.build_base, 'test_results')
        os.makedirs(test_results_path, exist_ok=True)

        try:
            env = await get_command_environment(
                'test', args.build_base, self.context.dependencies)
        except RuntimeError as e:
            logger.error(str(e))
            return 1

        if CARGO_EXECUTABLE is None:
            raise RuntimeError("Could not find 'cargo' executable")

        # invoke cargo test
        rc, stdout = await check_call_return_stdout(
            self.context,
            [CARGO_EXECUTABLE, 'test', '-q',
             '--target-dir', test_results_path,
             '--', '-Z', 'unstable-options', '--format=json'
             ],
            cwd=args.path, env=env, use_pty=True)

        cargo_json_to_xml(stdout, test_results_path + '/tests_report.xml')

        if rc.returncode:
            self.context.put_event_into_queue(TestFailure(pkg.name))
            # the return code should still be 0
        return 0


def cargo_json_to_xml(stdout, output_filename):
    root = Element('testsuites')
    testsuite = None
    total_tests = 0
    total_failures = 0
    for line in stdout:
        obj = json.loads(line)
        if obj['type'] == 'suite':
            if obj['event'] == 'started':
                testsuite = SubElement(root, 'testsuite')
                testsuite.set('tests', str(obj['test_count']))
                total_tests += int(obj['test_count'])
            else:
                if testsuite is not None:
                    testsuite.set('failures', str(obj['failed']))
                    total_failures += int(obj['failed'])
        if testsuite is not None:
            if obj['type'] == 'test':
                if obj['event'] == 'ok':
                    SubElement(testsuite, 'testcase', {'name': obj['name']})
                elif obj['event'] == 'failed':
                    test = SubElement(testsuite, 'testcase', {'name': obj['name']})
                    f = SubElement(test, 'failure')
                    f.text = obj['stdout']

    root.set('tests', str(total_tests))
    root.set('failures', str(total_failures))
    et = ElementTree(root)
    et.write(output_filename)


async def check_call_return_stdout(
        context, cmd, *, cwd=None, env=None, shell=False, use_pty=None
):
    """
    Run the command described by cmd.

    Post a `Command` event to the queue describing the exact invocation in
    order to allow reproducing it.
    All output to `stdout` and `stderr` is posted as `StdoutLine` and
    `StderrLine` events to the event queue.

    :param cmd: The command and its arguments
    :param cwd: the working directory for the subprocess
    :param env: a dictionary with environment variables
    :param shell: whether to use the shell as the program to execute
    :param use_pty: whether to use a pseudo terminal
    :returns: the result of the completed process and aggregated stdout
    """
    stdout = []

    def stdout_callback(line):
        context.put_event_into_queue(StdoutLine(line))
        stdout.append(line)

    def stderr_callback(line):
        context.put_event_into_queue(StderrLine(line))

    context.put_event_into_queue(
        Command(cmd, cwd=cwd, env=env, shell=shell))
    rc = await run(
        cmd, stdout_callback, stderr_callback,
        cwd=cwd, env=env, shell=shell, use_pty=use_pty)
    context.put_event_into_queue(
        CommandEnded(
            cmd, cwd=cwd, env=env, shell=shell, returncode=rc.returncode))
    return rc, stdout
