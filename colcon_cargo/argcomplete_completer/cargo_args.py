# Copyright 2018 Easymov Robotics
# Licensed under the Apache License, Version 2.0

# try import since this package doesn't depend on colcon-argcomplete
try:
    from colcon_argcomplete.argcomplete_completer \
        import ArgcompleteCompleterExtensionPoint
except ImportError:
    class ArgcompleteCompleterExtensionPoint:  # noqa: D101
        pass
from colcon_core.plugin_system import satisfies_version


class CargoArgcompleteCompleter(ArgcompleteCompleterExtensionPoint):
    """Completion of Cargo arguments."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            ArgcompleteCompleterExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')

    def get_completer(self, parser, *args, **kwargs):  # noqa: D102
        if '--cargo-args' not in args:
            return None

        try:
            from argcomplete.completers import ChoicesCompleter
        except ImportError:
            return None

        return ChoicesCompleter([])
