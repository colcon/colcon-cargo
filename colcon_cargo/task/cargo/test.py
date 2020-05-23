# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

import os

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
        rc = await run(
            self.context,
            [CARGO_EXECUTABLE, 'test', '-q',
                '--target-dir', test_results_path],
            cwd=args.path, env=env)

        if rc.returncode:
            self.context.put_event_into_queue(TestFailure(pkg.name))
            # the return code should still be 0
        return 0
