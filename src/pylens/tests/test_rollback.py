# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from pylens.exceptions import LensException
from pylens.rollback import Rollbackable, automatic_rollback


def test_rollbackable():
    class SomeClass(Rollbackable):
        def __init__(self, x, y):
            self.x, self.y = x, y

    o = SomeClass(1, [3, 4])
    state1 = o._get_state()
    o.x = 3
    o.y.append(16)
    assert o.x == 3
    assert o.y == [3, 4, 16]

    o._set_state(state1)
    assert o.x == 1
    assert o.y == [3, 4]

    # Test value comparision.
    o1 = SomeClass(1, [3, 4])
    o2 = SomeClass(1, [3, 4])
    assert o1 == o2
    o2.y[1] = 9
    assert o1 != o2
    o2.y[1] = 4
    assert o1 == o2


def test_automatic_rollback():
    class SomeClass(Rollbackable):
        def __init__(self, x, y):
            self.x, self.y = x, y

    o_1 = SomeClass(1, [3, 4])
    o_2 = None  # Important that we can handle None to simplify code.
    o_3 = SomeClass(1, [3, 4])

    try:
        with automatic_rollback(o_1, o_2, o_3):
            o_1.x = 3
            o_3.y.append(16)
            assert o_1.x == 3
            assert o_3.y == [3, 4, 16]
            raise LensException()  # In practice we will usually use LensException
    except LensException:
        pass  # Don't wish to stop test run.

    # Check we rolled back.
    assert o_1.x == 1
    assert o_3.y == [3, 4]
