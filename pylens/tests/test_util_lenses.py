from pytest import raises

from pylens.base_lenses import AnyOf
from pylens.charsets import alphanums, alphas, nums
from pylens.debug import assert_equal, describe_test
from pylens.exceptions import LensException
from pylens.readers import ConcreteInputReader
from pylens.settings import GlobalSettings
from pylens.util_lenses import List, NewLine, OneOrMore, Optional, Whitespace, Word


def d(*args):
    print(args)


def test_one_or_more():
    # This is really just to check the lens construction.
    lens = OneOrMore(AnyOf(nums, type=int), type=list)
    assert lens.get("123") == [1, 2, 3]


def test_optional():
    GlobalSettings.check_consumption = False
    lens = Optional(AnyOf(alphas, type=str))
    assert lens.get("abc") == "a"
    assert lens.get("123") == None
    assert lens.put("a") == "a"
    assert lens.put(1) == ""


def test_list():
    lens = List(AnyOf(nums, type=int), ",", type=list)
    d("GET")
    assert lens.get("1,2,3") == [1, 2, 3]
    d("PUT")
    assert lens.put([6, 2, 6, 7, 4, 8]) == "6,2,6,7,4,8"

    # It was getting flattened due to And within And!
    describe_test("Test a bug I found with nested lists.")
    INPUT = "1|2,3|4,5|6"
    lens = List(
        List(AnyOf(nums, type=int), "|", name="inner_list", type=list),
        ",",
        name="outer_list",
        type=list,
    )
    got = lens.get(INPUT)
    assert_equal(got, [[1, 2], [3, 4], [5, 6]])
    got.insert(2, [6, 7])
    assert_equal(lens.put(got), "1|2,3|4,6|7,5|6")


def test_newline():
    lens = NewLine()
    assert lens.get("\n") == None
    assert lens.get("") == None
    with raises(LensException):
        lens.get("abc")
    assert lens.put("\n") == "\n"


def test_word():
    GlobalSettings.check_consumption = False

    lens = Word(alphanums, init_chars=alphas, type=str, max_count=5)
    d("GET")
    assert lens.get("w23dffdf3") == "w23df"
    with raises(LensException):
        assert lens.get("1w23dffdf3") == "w23df"

    d("PUT")
    assert lens.put("R2D2") == "R2D2"

    with raises(LensException):
        lens.put("2234") == "R2D2"

    # XXX: Should fail if length checking working correctly.
    # with raises(LensException) :
    #  lens.put("TooL0ng")

    d("Test with no type")
    lens = Word(alphanums, init_chars=alphas, max_count=5, default="a123d")
    assert lens.get("w23dffdf3") == None
    concrete_input_reader = ConcreteInputReader("ab12_3456")
    assert lens.put(None, concrete_input_reader) == "ab12"
    assert concrete_input_reader.get_remaining() == "_3456"
    assert lens.put() == "a123d"


def test_whitespace():
    GlobalSettings.check_consumption = False

    # Simple whitespace.
    lens = Whitespace(" ")
    concrete_input_reader = ConcreteInputReader("  \t  xyz")
    assert (
        lens.get(concrete_input_reader) == None
        and concrete_input_reader.get_remaining() == "xyz"
    )
    assert lens.put() == " "

    # Test that the Empty lens is valid when the default space is set to empty string (i.e. not space).
    lens = Whitespace("")
    assert lens.get("xyz") == None
    assert lens.put() == ""

    # With slash continuation.
    lens = Whitespace(" ", slash_continuation=True)
    concrete_input_reader = ConcreteInputReader("  \t\\\n  xyz")
    assert (
        lens.get(concrete_input_reader) == None
        and concrete_input_reader.get_remaining() == "xyz"
    )

    # With indent continuation.
    lens = Whitespace(" ", indent_continuation=True)
    concrete_input_reader = ConcreteInputReader("  \n xyz")
    assert (
        lens.get(concrete_input_reader) == None
        and concrete_input_reader.get_remaining() == "xyz"
    )
