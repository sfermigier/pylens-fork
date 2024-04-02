# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from pylens.debug import d
from pylens.util import Properties


def test_properties():
    d("Testing")
    properties = Properties(food="cheese")
    assert properties.food == "cheese"
    properties.something = [1, 2, 3]
    assert properties.something == [1, 2, 3]
    assert properties.nothing is None
