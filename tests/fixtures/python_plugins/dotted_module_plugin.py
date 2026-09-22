"""Fixture: a Python plugin loaded by dotted module name in `python_plugins:`
(the test adds this file's directory to sys.path so `import dotted_module_plugin`
resolves)."""

import bsm_scanner


def quadruple(args, options):
    return args["value"] * 4.0


bsm_scanner.register_plugin_function("fixture_dotted_module_plugin", "quadruple", quadruple)
