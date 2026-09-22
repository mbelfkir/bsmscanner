"""Fixture: a Python plugin loaded via a file path in `python_plugins:`."""

import bsm_scanner

LOAD_COUNT = 0


def triple(args, options):
    global LOAD_COUNT
    return args["value"] * 3.0


bsm_scanner.register_plugin_function("fixture_file_path_plugin", "triple", triple)
LOAD_COUNT += 1
