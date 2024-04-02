# Copyright (c) 2010-2011, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from pylens.util import Properties, has_value

META_ATTRIBUTE = "_meta_data"


#
# Wrappers for simple types, so we can transparently add arbitrary properies.
#
class str_wrapper(str):
    pass


class int_wrapper(int):
    pass


class float_wrapper(float):
    pass


class list_wrapper(list):
    pass


class dict_wrapper(dict):
    pass


def item_has_meta(item):
    return hasattr(item, META_ATTRIBUTE)


def enable_meta_data(item):
    """
    If not already present, this adds a flexible Properties attribute to any
    object for storing meta data (e.g. information about the concrete origin of
    an extracted item).

    Note that, since some builtin python types cannot hold
    arbitrary attributes, we wrap them thinly in appropriate classes.
    """
    assert has_value(item)

    if not item_has_meta(item):
        # Wrap simple types to allow attributes to be added to them.
        if isinstance(item, str):
            item = str_wrapper(item)
        elif isinstance(item, float):
            item = float_wrapper(item)
        elif isinstance(item, int):
            item = int_wrapper(item)
        elif isinstance(item, list):
            item = list_wrapper(item)
        elif isinstance(item, dict):
            item = dict_wrapper(item)

        setattr(item, META_ATTRIBUTE, Properties())

    return item
