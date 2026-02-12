# Copyright 2026 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from pathlib import Path
from unittest.mock import patch

from colcon_cargo.package_augmentation.cargo \
    import create_dependency_descriptor
import pytest


VERSION_CONSTRAINTS = {
    None: {},
    '': {},
    '1.2.3': {'version_gte': '1.2.3', 'version_lt': '2'},
    '1.2': {'version_gte': '1.2', 'version_lt': '2'},
    '1': {'version_gte': '1', 'version_lt': '2'},
    '0.2.3': {'version_gte': '0.2.3', 'version_lt': '0.3'},
    '0.2': {'version_gte': '0.2', 'version_lt': '0.3'},
    '0.0.3': {'version_gte': '0.0.3', 'version_lt': '0.0.4'},
    '0.0': {'version_gte': '0.0', 'version_lt': '0.1'},
    '0': {'version_gte': '0', 'version_lt': '1'},
    '^ 1.2.3': {'version_gte': '1.2.3', 'version_lt': '2'},
    '^ 1.2': {'version_gte': '1.2', 'version_lt': '2'},
    '^ 1': {'version_gte': '1', 'version_lt': '2'},
    '^ 0.2.3': {'version_gte': '0.2.3', 'version_lt': '0.3'},
    '^ 0.2': {'version_gte': '0.2', 'version_lt': '0.3'},
    '^ 0.0.3': {'version_gte': '0.0.3', 'version_lt': '0.0.4'},
    '^ 0.0': {'version_gte': '0.0', 'version_lt': '0.1'},
    '^ 0': {'version_gte': '0', 'version_lt': '1'},
    '~ 1.2.3': {'version_gte': '1.2.3', 'version_lt': '1.3'},
    '~ 1.2': {'version_gte': '1.2', 'version_lt': '1.3'},
    '~ 1': {'version_gte': '1', 'version_lt': '2'},
    '*': {'version_gte': '0'},
    '1.*': {'version_gte': '1', 'version_lt': '2'},
    '1.2.*': {'version_gte': '1.2', 'version_lt': '1.3'},
    '>=1.*': {'version_gte': '1'},
    '<1.2.*': {'version_lt': '1.2'},
    '>= 1.2.3': {'version_gte': '1.2.3'},
    '<= 1.2.3': {'version_lte': '1.2.3'},
    '= 1.2.3': {'version_eq': '1.2.3'},
    '> 1.2.3': {'version_gt': '1.2.3'},
    '< 1.2.3': {'version_lt': '1.2.3'},
    '>1.2.3, <=2.0': {'version_gt': '1.2.3', 'version_lte': '2.0'},
}


@pytest.mark.parametrize('constraints', list(VERSION_CONSTRAINTS.keys()))
def test_create_dependency_descriptor(constraints):
    metadata = {
        **VERSION_CONSTRAINTS[constraints],
    }

    dep = create_dependency_descriptor('dependency', constraints, Path.cwd())
    assert 'dependency' == dep.name
    assert metadata == {k: v for k, v in dep.metadata.items() if k in metadata}


@pytest.mark.parametrize('constraints', ['1.*.3', '*.*.3', '*.2'])
def test_create_dependency_descriptor_unsupported(constraints):
    with patch(
        'colcon_cargo.package_augmentation.cargo.logger.warning',
    ) as log:
        dep = create_dependency_descriptor(
            'dependency', constraints, Path.cwd())

    # No constraint in the metadata
    assert 'dependency' == dep.name
    assert not any(k.startswith('version_') for k in dep.metadata.keys())

    # Single call to logger.warning()
    assert log.call_count == 1
    assert len(log.call_args[0]) >= 1
    assert 'unsupported' in log.call_args[0][0]
