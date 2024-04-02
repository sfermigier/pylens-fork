# ruff: noqa

# Copyright (c) 2010-2011, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

# Optionally include nbdebug functions.
try:
    from nbdebug import IN_DEBUG_MODE, breakpoint, d, set_indent_function
except:
    d = lambda x: None
    set_indent_function = None
    IN_DEBUG_MODE = False


# More syntacticaly consistant assert function, for displaying explanations
def assert_msg(condition, msg=None):
    assert condition, msg or ""


def describe_test(msg):
    """A debug message that will stand out."""
    msg = "========= " + msg + " ========="
    return d(msg)


def assert_equal(got, expected):
    assert_msg(got == expected, f"Expected >>>{expected}<<< but got >>>{got}<<<")


def auto_name_lenses(local_variables):
    """
    Gives names to lenses based on their local variable names, which is
    useful for tracing parsing. Should be called with globals()/locals()
    """
    from pylens.base_lenses import Lens

    for variable_name, obj in local_variables.items():
        if isinstance(obj, Lens):
            obj.name = variable_name


# Set a debug message indentation function if the debug library is in use.
if set_indent_function:

    def debug_indent_function():
        """
        Nicely indents the debug messages according to the hierarchy of lenses.
        """
        import inspect

        # Create a list of all function names in the trace.
        function_names = []

        # Prepend the callers location to the message.
        callerFrame = inspect.currentframe()
        while callerFrame:
            location = callerFrame.f_code.co_name
            function_names.append(location)
            callerFrame = callerFrame.f_back

        indent = 0
        # Includes 'get' and 'put' since get may be called directly in put (not _put), etc.
        for name in ["_put", "_get", "put", "get"]:
            indent += function_names.count(name)
        indent -= 1
        indent = max(0, indent)

        return " " * indent

    set_indent_function(debug_indent_function)
