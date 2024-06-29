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
        """
        Get the completer for Cargo arguments.

        This method checks if the '--cargo-args' argument is present in the provided arguments.
        If it is, it tries to import the ChoicesCompleter from the argcomplete package and returns
        an instance of it with an empty list of choices. If the '--cargo-args' argument is not
        present or the argcomplete package is not installed, it returns None.

        Args:
            parser: The argument parser.
            *args: Positional arguments passed to the method.
            **kwargs: Keyword arguments passed to the method.

        Returns:
            ChoicesCompleter or None: An instance of ChoicesCompleter with an empty list of choices,
            or None if the '--cargo-args' argument is not present or the argcomplete package is not
            installed.
        """
        if "--cargo-args" not in args:
            return None

        try:
            from argcomplete.completers import ChoicesCompleter
        except ImportError:
            return None

        return ChoicesCompleter([])
