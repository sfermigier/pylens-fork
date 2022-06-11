from pylens.base_lenses import And, AnyOf, Empty, Group, Literal, Repeat
from pylens.charsets import alphas, nums
from pylens.debug import assert_equal, assert_raises, auto_name_lenses, describe_test
from pylens.exceptions import (
    LensException,
    NoDefaultException,
    TooFewIterationsException,
)
from pylens.readers import ConcreteInputReader
from pylens.settings import GlobalSettings


def d(*args):
    print(*args)


def test_and():
    d("GET")
    lens = And(AnyOf(alphas, type=str), AnyOf(nums, type=int), type=list)
    got = lens.get("m0")
    assert got == ["m", 0]

    d("PUT")
    got[0] = "d"  # Modify an item, though preserving list source info in meta.
    assert lens.put(got) == "d0"

    d("CREATE")  # The new list and items will hold no meta.
    assert lens.put(["z", 8]) == "z8"

    d("Input alignment test")
    # Now test alignment of input with a more complex lens
    sub_lens = Group(
        AnyOf(alphas, type=str) + AnyOf("*+", default="*") + AnyOf(nums, type=int),
        type=list,
    )
    lens = Group(sub_lens + sub_lens, type=list)
    auto_name_lenses(locals())
    got = lens.get("a+3x*6")
    assert got == [["a", 3], ["x", 6]]

    # Now re-order the items
    got.append(got.pop(0))
    output = lens.put(got)
    # And the non-stored input (i.e. '*' and '+') should have been carried with the abstract items.
    assert output == "x*6a+3"

    # And for CREATE, using default value for non-store lens.
    output = lens.put([["b", 9], ["c", 4]])
    assert output == "b*9c*4"


def test_or():
    d("GET")
    lens = AnyOf(alphas, type=str) | AnyOf(nums, type=int)
    concrete_input_reader = ConcreteInputReader("abc")
    got = lens.get(concrete_input_reader)
    assert got == "a" and concrete_input_reader.get_remaining() == "bc"
    concrete_input_reader = ConcreteInputReader("123")
    got = lens.get(concrete_input_reader)
    assert got == 1 and concrete_input_reader.get_remaining() == "23"

    d("PUT")
    # Test straight put
    concrete_input_reader = ConcreteInputReader("abc")
    assert (
        lens.put("p", concrete_input_reader) == "p"
        and concrete_input_reader.get_remaining() == "bc"
    )

    # Test cross put
    concrete_input_reader = ConcreteInputReader("abc")
    assert lens.put(4, concrete_input_reader) == "4"
    assert concrete_input_reader.get_remaining() == "bc"

    d("Test with default values")
    lens = AnyOf(alphas, type=str) | AnyOf(nums, default=3)
    assert lens.put() == "3"
    assert lens.put("r") == "r"

    # And whilst we are at it, check the outer lens default overrides the inner lens.
    lens.default = "x"
    assert lens.put() == "x"

    d("Test sensible handling of Empty lens.")
    # Actually, this issue (if not fixed) will manifest only if we use container.
    lens = AnyOf(alphas, type=str) | Empty()
    concrete_input_reader = ConcreteInputReader("b4")
    assert (
        lens.put("4", concrete_input_reader) == ""
        and concrete_input_reader.get_remaining() == "4"
    )

    d("Test sensible handling of Empty lens with container.")
    lens = Group((AnyOf(alphas, type=str) | Empty()) + AnyOf(nums, type=int), type=list)
    concrete_input_reader = ConcreteInputReader("a4")
    got = lens.get(concrete_input_reader)
    assert got == ["a", 4]

    # We expect that: put char that is not in alphas, so Empty used, yet full string consumed.
    # This is an important test that OR works as expected (i.e. according to the
    # ordering of operand lenses) with a lens such as
    # Empty()
    concrete_input_reader.reset()
    del got[0]  # Important that we use 'got' so input is aligned.
    assert lens.put(got, concrete_input_reader) == "4"
    assert concrete_input_reader.is_fully_consumed()


def test_any_of():
    lens = AnyOf(alphas, type=str, some_property="some_val")
    assert (
        lens.options.some_property == "some_val"
    )  # Might as well test lens options working.

    d("GET")
    got = lens.get("m")
    assert got == "m"

    # Test putting back what we got (i.e. with meta)
    d("PUT")
    assert lens.put(got) == "m"

    d("CREATE")
    output = lens.put("d")
    assert output == "d"

    d("Test default of non-typed lens is created")
    lens = AnyOf(alphas, default="x")
    output = lens.put()
    assert output == "x"

    d("Test failure when default value required.")
    lens = AnyOf(alphas)
    with assert_raises(NoDefaultException):
        lens.put()

    d("TEST type coercion")
    lens = AnyOf(nums, type=int)
    assert lens.get("3") == 3
    assert lens.put(8) == "8"

    # Check default converted to string.
    lens = AnyOf(nums, default=5)
    assert lens.put() == "5"


def test_repeat():
    # Note, for some of these tests we need to ensure we PUT rather than CREATE
    # the lists so we can flex the code when input is aligned.

    lens = Repeat(AnyOf(nums, type=int), min_count=3, max_count=5, type=list)
    d("GET")
    assert lens.get("1234") == [1, 2, 3, 4]

    with assert_raises(TooFewIterationsException):
        lens.get("12")
    # Test max_count
    assert lens.get(ConcreteInputReader("12345678")) == [1, 2, 3, 4, 5]

    describe_test("Put as many as were there originally.")
    input_reader = ConcreteInputReader("98765")
    assert (
        lens.put([1, 2, 3, 4, 5], input_reader) == "12345"
        and input_reader.get_remaining() == ""
    )

    describe_test("Put a maximum (5) of the items (6)")
    input_reader = ConcreteInputReader("987654321")
    GlobalSettings.check_consumption = False
    assert (
        lens.put([1, 2, 3, 4, 5, 6], input_reader) == "12345"
        and input_reader.get_remaining() == "4321"
    )
    GlobalSettings.check_consumption = True

    describe_test("Put more than there were originally.")
    input_reader = ConcreteInputReader("981abc")
    got = lens.get(input_reader)
    got.insert(2, 3)
    input_reader.reset()
    assert_equal(lens.put(got, input_reader), "9831")
    assert_equal(input_reader.get_remaining(), "abc")

    describe_test(
        "PUT fewer than got originally, but consume up to max from the input."
    )
    input_reader = ConcreteInputReader("87654321")
    got = lens.get(input_reader)
    del got[2]  # Remove the 6
    input_reader.reset()
    assert lens.put(got, input_reader) == "8754"
    assert input_reader.get_remaining() == "321"

    describe_test("Test non-typed lenses.")
    lens = Repeat(AnyOf(nums, default=8))
    input_reader = ConcreteInputReader("12345abc")
    d(lens.get(input_reader) == None and input_reader.get_remaining() == "abc")
    input_reader.reset()
    # Lens should make use of outer input, since not supplied by an item.
    assert (
        lens.put(None, input_reader, None) == "12345"
        and input_reader.get_remaining() == "abc"
    )

    describe_test("Test the functionality without default values.")
    # Should fail, since lens has no default, so could put infinite items.
    with assert_raises(LensException):
        lens.put()

    describe_test("Test the functionality with default value on Repeat.")
    lens = Repeat(AnyOf(nums), default="54321")
    assert lens.put() == "54321"

    d("Test putting back what we got (i.e. with source meta)")
    lens = Repeat(AnyOf(nums, type=int), type=list)
    assert lens.put(lens.get("1234")) == "1234"

    d("Test for completeness")
    GlobalSettings.check_consumption = False
    lens = Repeat(AnyOf(nums, type=int), type=list, min_count=0, max_count=1)
    assert lens.get("abc") == []  # No exception thrown since min_count == 0
    assert lens.get("123abc") == [1]  # Since max_count == 1
    assert lens.put([1, 2, 3]) == "1"  # Since max_count == 1

    d("Test combine_chars")
    lens = Repeat(AnyOf(alphas, type=str), type=list, combine_chars=True)
    assert lens.get("abc123") == "abc"
    assert lens.put("xyz") == "xyz"

    GlobalSettings.check_consumption = True

    d("Test infinity problem")
    lens = Repeat(Empty(), min_count=3, max_count=None)
    # Will fail to get anything since Empty lens changes no state.
    with assert_raises(LensException):
        lens.get("anything")
    # Likewise.
    with assert_raises(LensException):
        lens.put(None)

    d("Test the functionality with default value on sub-lens.")
    lens = Repeat(AnyOf(nums, default=4))
    # Should faile since no input or items are consumed by the lens.
    with assert_raises(LensException):
        lens.put()


def test_empty():
    GlobalSettings.check_consumption = False

    d("Test with type")
    lens = Empty(type=str)
    assert lens.get("anything") == ""
    assert lens.put("", "anything") == ""
    with assert_raises(LensException):
        lens.put(" ", "anything")

    assert lens.put("") == ""

    d("Test without type")
    lens = Empty()
    assert lens.get("anything") == None
    assert lens.put() == ""
    # Lens does not expect to put an item, valid or otherwise.
    with assert_raises(LensException):
        lens.put("", "anything")

    d("Test special modes.")
    lens = Empty(mode=Empty.START_OF_TEXT)
    concrete_reader = ConcreteInputReader("hello")
    # Progress the input reader so lens does not match.
    concrete_reader.consume_char()
    with assert_raises(LensException):
        lens.get(concrete_reader)

    lens = Empty(mode=Empty.END_OF_TEXT)
    concrete_reader = ConcreteInputReader("h")
    # This should throw an Exception
    with assert_raises(LensException):
        lens.get(concrete_reader)
    concrete_reader.consume_char()
    # This should succeed quietly.
    lens.get(concrete_reader)


def test_group():
    GlobalSettings.check_consumption = False

    d("GET")
    lens = Group(AnyOf(alphas, type=str) + AnyOf(nums, type=int), type=list)
    got = lens.get("a2b3")
    d(got)
    assert got == ["a", 2]

    d("PUT")
    assert lens.put(got, "n6b3") == "a2"

    d("CREATE")
    assert lens.put(["x", 4]) == "x4"

    d("TEST erroneous Group with no type")
    with assert_raises(AssertionError):
        lens = Group(AnyOf(nums))


def test_litteral():
    d("GET")
    lens = Literal("xyz")
    concrete_reader = ConcreteInputReader("xyzabc")
    assert (
        lens.get(concrete_reader) == None and concrete_reader.get_remaining() == "abc"
    )
    d("PUT")
    assert lens.put(None) == "xyz"

    # XXX: Need to think more about this, and what it impacts.
    # Should flag that we mistakenly passed an item to a non-store low-level
    # lens that could not possibly us it.
    # with assert_raises(LensException) :
    #  lens.put("xyz")

    d("Test as STORE lens, pointless as it is with this lens.")
    lens = Literal("xyz", type=str)
    concrete_reader = ConcreteInputReader("xyzabc")
    assert (
        lens.get(concrete_reader) == "xyz" and concrete_reader.get_remaining() == "abc"
    )
    concrete_reader = ConcreteInputReader("xyzabc")
    assert (
        lens.put("xyz", concrete_reader) == "xyz"
        and concrete_reader.get_remaining() == "abc"
    )
