# Copyright (c) 2010-2011, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause


class GlobalSettings:
    """
    These are some global settings that affect the functionality of the
    framework.
    """

    """
    Check that the (outer most) lens fully consumes the
    input string and that containers are fully consumed in the PUT direction,
    where is possible to know such a thing.
    You might wish to set this to False when developing or debugging your own lenses.
    """
    check_consumption = True
