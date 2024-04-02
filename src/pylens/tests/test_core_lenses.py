# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from pytest import raises

from pylens.base_lenses import AnyOf, Group
from pylens.charsets import alphas
from pylens.core_lenses import Forward, Until
from pylens.debug import d, describe_test
from pylens.exceptions import InfiniteRecursionException


def test_forward():
    # TODO: Need to think about semantics of this and how it will work with groups.
    d("GET")
    lens = Forward()
    # Now define the lens (must use '<<' rather than '=', since cannot easily
    # override '=').
    lens << "[" + (AnyOf(alphas, type=str) | lens) + "]"

    # Ensure the lens is enclosed in a container lens.
    lens = Group(lens, type=list)

    got = lens.get("[[[h]]]")
    assert got == ["h"]

    d("PUT")
    got[0] = "p"
    output = lens.put(got)
    assert output == "[[[p]]]"

    # Note that this lens results in infinite recursion upon CREATE.
    d("CREATE")
    output = lens.put(["k"])
    assert output == "[k]"

    # If we alter the grammar slightly, we will get an infinite recursion error,
    # since the lens could recurse to an infinite depth before considering the
    # AnyOf() lens.
    lens = Forward()
    lens << "[" + (lens | AnyOf(alphas, type=str)) + "]"
    lens = Group(lens, type=list)
    with raises(InfiniteRecursionException):
        output = lens.put(["k"])


def test_until():
    d("GET")
    lens = Group("(" + Until(")", type=str) + ")", type=list)
    got = lens.get("(in the middle)")
    assert got == ["in the middle"]

    d("PUT")
    output = lens.put(["monkey"])
    assert output == "(monkey)"

    describe_test("Try with include_lens=True")
    assert lens.get(lens.put(["monkey"])) == ["monkey"]
    lens = Group("(" + Until(")", type=str, include_lens=True), type=list)
    got = lens.get("(in the middle)")
    assert got == ["in the middle)"]

    # XXX: Perhaps protect against this, or perhaps leave to lens user to worry about?!
    # assert(lens.get(lens.put(["mon)key"])) == ["monkey"])
