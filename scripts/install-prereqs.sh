#!/usr/bin/env bash
pip install --upgrade setuptools \
    git+https://github.com/colcon/colcon-core \
    git+https://github.com/colcon/colcon-library-path \
    pytest pytest-cov \
    pyenchant \
    flake8-blind-except flake8-builtins flake8-class-newline \
    flake8-comprehensions flake8-deprecated flake8-docstrings flake8-quotes \
    pep8-naming pylint

