# ruff: noqa

#
# Copyright (c) 2010-2011, Nick Blundell
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Nick Blundell nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#
#
# Author: Nick Blundell <blundeln [AT] gmail [DOT] com>
# Organisation: www.nickblundell.org.uk
#
# Description:
#   Isolates all debugging functions.

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
