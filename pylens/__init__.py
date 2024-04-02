# Copyright (c) 2010-2011, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Main API functions for using pylens.
"""

# Imports all lenses, some indirectly.
# from util_lenses import *


##################################
# High-level API functions
##################################

# Hmmm, do we really need these.

# COuld write Person.get() -> person and person.put()
from pylens.base_lenses import Lens
from pylens.containers import LensObject
from pylens.debug import assert_msg
from pylens.util_lenses import AutoGroup


def get(lens, *args, **kargs):
    """
    Extracts a python structure from some string structure using the given
    lens, ensuring that the lens parameter is conveniently coerced to an
    appropriate Lens class.

    Example::

      get(Person, "Person::name=nick,surname=blundell") -> instance of Person class.
    """
    lens = Lens._coerce_to_lens(lens)
    # Wrap in AutoGroup, so outer container may be ommitted for convenience
    # (usually of testing lens fragments)
    if not lens.has_type():
        lens = AutoGroup(lens)
    return lens.get(*args, **kargs)


def put(lens_or_instance, *args, **kargs):
    """
    Puts some python structure back into some string structure.

    Example: put(some_lens, {"a":1, "c":4}) -> "a=1,c=4"
    """
    # If we have an instance of a class which defines its own lens...
    if isinstance(
        lens_or_instance, LensObject
    ):  # and hasattr(lens_or_instance, "__lens__") :
        assert_msg(
            hasattr(lens_or_instance, "__lens__"),
            f"LensObject {lens_or_instance} defines no __lens__",
        )
        lens = Lens._coerce_to_lens(lens_or_instance.__class__)
        instance = lens_or_instance  # For clarity.
        return lens.put(instance, *args, **kargs)

    # Otherwise...
    lens = Lens._coerce_to_lens(lens_or_instance)
    # Wrap in AutoGroup, so outer container may be ommitted for convenience
    # (usually of testing lens fragments). We assume above that instance will be
    # wrapped in am appropriately typed group, so only do this here.
    if not lens.has_type():
        lens = AutoGroup(lens)

    return lens.put(*args, **kargs)
