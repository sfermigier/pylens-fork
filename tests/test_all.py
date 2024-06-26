# Copyright (c) 2010, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Longer tests.
Some of these are based on tricky config file examples given in the Augeas system
Note that these lenses may not be completely accurate but are an aid to testing.
"""

from pytest import raises

from pylens import get, put
from pylens.base_lenses import AnyOf, Group, Repeat
from pylens.charsets import alphas, nums
from pylens.containers import MODEL, SOURCE, Container, LensObject
from pylens.core_lenses import Until
from pylens.debug import assert_equal, describe_test
from pylens.exceptions import NotFullyConsumedException, NoTokenToConsumeException
from pylens.settings import GlobalSettings
from pylens.util_lenses import (
    NL,
    WS,
    BlankLine,
    HashComment,
    KeyValue,
    Keyword,
    List,
    Word,
    ZeroOrMore,
)


def d(*args):
    print(*args)


def test_auto_list():
    lens = Repeat(AnyOf(nums, type=int), type=list, auto_list=True)
    d("GET")
    assert lens.get("123") == [1, 2, 3]
    assert lens.get("1") == 1

    d("PUT")
    assert lens.put([5, 6, 7]) == "567"
    assert lens.put(5) == "5"

    # Test list_source_meta_data preservation - assertion will fail if not preserved.
    assert lens.put(lens.get("1")) == "1"


def test_dict():
    # Test use of static labels.
    lens = Group(
        AnyOf(nums, type=int, label="number")
        + AnyOf(alphas, type=str, label="character"),
        type=dict,
        alignment=SOURCE,
    )

    d("GET")
    assert lens.get("1a") == {"number": 1, "character": "a"}

    d("PUT")
    assert lens.put({"number": 4, "character": "q"}, "1a") == "4q"
    with raises(NoTokenToConsumeException):
        lens.put({"number": 4, "wrong_label": "q"}, "1a")

    # Test dynamic labels
    key_value_lens = Group(
        AnyOf(alphas, type=str, is_label=True)
        + AnyOf("*+-", default="*")
        + AnyOf(nums, type=int),
        type=list,
    )
    lens = Repeat(key_value_lens, type=dict, alignment=SOURCE)

    d("GET")
    got = lens.get("a+3c-2z*7")
    d(got)
    assert got == {"a": [3], "c": [2], "z": [7]}

    d("PUT")
    output = lens.put({"b": [9], "x": [5]})
    d(output)
    assert output in ["b*9x*5", "x*5b*9"]  # Could be any order.

    d("Test manipulation")
    got = lens.get("a+3c-2z*7")
    del got["c"]
    output = lens.put(got)
    assert output == "a+3z*7"  # Should have kept SOURCE alignment.

    d("Test with auto list, which should keep source state")
    key_value_lens = Group(
        AnyOf(alphas, type=str, is_label=True)
        + AnyOf("*+-", default="*")
        + AnyOf(nums, type=int),
        type=list,
        auto_list=True,
    )
    lens = Repeat(key_value_lens, type=dict, alignment=SOURCE)

    d("GET")
    got = lens.get("a+3c-2z*7")
    d(got)
    assert got == {"a": 3, "c": 2, "z": 7}
    d("PUT")
    output = lens.put(got)
    assert output == "a+3c-2z*7"

    # For now this will loose some concrete, but later we will consider user-implied alignment
    # or at least label alignment rather than source alignment.
    d("Test auto_list with modification.")
    got = lens.get("a+3c-2z*7")
    got["c"] = 4
    output = lens.put(got)
    assert_equal(output, "a+3z*7c*4")


def test_consumption():
    describe_test("Test input consumption")

    lens = Repeat(AnyOf(nums, type=int), type=list)
    with raises(NotFullyConsumedException):
        lens.get("123abc")  # This will leave 'abc'

    with raises(NotFullyConsumedException):
        lens.put([1, 2], "123abc")  # This will leave 'abc'

    describe_test("Test container consumption")

    # This will consume input but leave "a" in list.
    with raises(NotFullyConsumedException):
        lens.put([1, 2, "a"], "67")


def test_list():
    lens = Repeat(AnyOf(nums, type=int), type=list)
    d("GET")
    assert lens.get("123") == [1, 2, 3]

    d("PUT")
    assert lens.put([5, 6, 7]) == "567"

    d("GET-PUT")
    assert lens.put(lens.get("1")) == "1"


def test_model_ordered_matching_list():
    lens = Repeat(
        Group(
            AnyOf(alphas, type=str) + AnyOf("*+-", default="*") + AnyOf(nums, type=int),
            type=list,
        ),
        type=list,
        alignment=MODEL,
    )

    d("GET")
    got = lens.get("a+3c-2z*7")
    assert got == [["a", 3], ["c", 2], ["z", 7]]

    # Move the front item to the end - should affect positional ordering.
    got.append(got.pop(0))

    output = lens.put(got)
    d(output)
    assert output == "c-2z*7a+3"

    d("With deletion and creation")
    d("GET")
    got = lens.get("a+3c-2z*7")
    # Move the front item to the end - should affect positional ordering.
    got.append(got.pop(0))
    # Now remove the middle item
    del got[1]  # z*7
    # And add a new item
    got.append(["m", 6])

    output = lens.put(got)
    d(output)
    assert output == "c-2a+3m*6"


def test_source_ordered_matching_list():
    lens = Repeat(
        Group(
            AnyOf(alphas, type=str) + AnyOf("*+-", default="*") + AnyOf(nums, type=int),
            type=list,
        ),
        type=list,
        alignment=SOURCE,
    )

    d("Without deletion")
    d("GET")
    got = lens.get("a+3c-2z*7")
    assert got == [["a", 3], ["c", 2], ["z", 7]]

    # Move the front item to the end - should affect positional ordering.
    got.append(got.pop(0))

    output = lens.put(got)
    d(output)
    assert_equal(output, "a+3c-2z*7")

    d("With deletion and creation")
    d("GET")
    got = lens.get("a+3c-2z*7")
    # Move the front item to the end - should affect positional ordering.
    got.append(got.pop(0))
    # Now remove the middle item
    del got[1]  # z*7
    # And add a new item
    got.append(["m", 6])

    output = lens.put(got)
    assert output == "a+3c-2m*6"


def test_state_recovery():
    describe_test("Test that the user's item's state is recovered after consumption.")
    INPUT = "x=y;p=q"
    lens = List(
        KeyValue(Word(alphas, is_label=True) + "=" + Word(alphas, type=str)),
        ";",
        type=dict,
    )
    got = lens.get(INPUT)
    my_dict = {}
    my_dict["beans"] = "yummy"
    my_dict["marmite"] = "eurgh"
    lens.put(my_dict)
    assert my_dict == {"beans": "yummy", "marmite": "eurgh"}
    # XXX: Actually, due to DictContainer implementation, this state would not be
    # lost anyway, though a similar test with LensObject below flexes this test
    # case.  I will leave this test, should the implemenation change in someway to
    # warrent this test case.


def test_lens_object():
    """
    Here we demonstrate the use of classes to define our data model which are
    related to a lens.
    """

    # Define our Person class, which internally defines its lens.
    class Person(LensObject):
        __lens__ = "Person::" + List(
            KeyValue(
                Word(alphas + " ", is_label=True) + ":" + Word(alphas + " ", type=str)
            ),
            ";",
            type=None,  # XXX: I should get rid of default list type on List
        )

        def __init__(self, name, last_name):
            self.name, self.last_name = name, last_name

    # Here we use the high-level API get() function, which is for convenience and
    # which equates to:
    #  lens = Group(Person.__lens__, type=Person)
    #  person = lens.get("Person::Name:nick;Last   Name:blundell")
    describe_test("GET")
    person = get(Person, "Person::Name:nick;Last   Name:blundell")
    assert person.name == "nick" and person.last_name == "blundell"

    # Now we PUT it back with no modification and should get what we started with.
    describe_test("PUT")
    output = put(person)
    assert output == "Person::Name:nick;Last   Name:blundell"

    # And we do this again to check the consumed state of person was restored
    # after the successful PUT.
    output = put(person)
    assert output == "Person::Name:nick;Last   Name:blundell"

    describe_test("CREATE")
    new_person = Person("james", "bond")
    output = put(new_person)

    # Test that consumed state is restored on a successful PUT.
    assert new_person.name == "james" and new_person.last_name == "bond"

    # XXX: Would be nice to control the order, but need to think of a nice way to
    # do this - need to cache source info of a label, which we can use when we
    # loose source info, also when a user declares attributes we can remember the
    # order and force this as model order.
    assert (
        output == "Person::Last   Name:bond;Name:james"
        or output == "Person::Name:james;Last   Name:bond"
    )
    got_person = get(Person, output)
    # If all went well, we should GET back what we PUT.
    assert got_person.name == "james" and got_person.last_name == "bond"


def test_constrained_lens_object():
    """
    Here we show how the user can constrain valid attributes of a LensObject.
    """
    return  # TODO


def test_advanced_lens_object():
    # Ref: http://manpages.ubuntu.com/manpages/hardy/man5/interfaces.5.html
    INPUT = """
iface eth0-home inet static
   address 192.168.1.1
   netmask 255.255.255.0
   gateway  67.207.128.1
   dns-nameservers 67.207.128.4 67.207.128.5
   up flush-mail

auto lo eth0
# A comment
auto eth1 
"""

    class NetworkInterface(LensObject):
        __lens__ = (
            "iface"
            + WS(" ")
            + Keyword(additional_chars="_-", is_label=True)
            + WS(" ")
            + Keyword(label="address_family")
            + WS(" ")
            + Keyword(label="method")
            + NL()
            + ZeroOrMore(
                KeyValue(
                    WS("   ")
                    + Keyword(additional_chars="_-", is_label=True)
                    + WS(" ")
                    + Until(NL(), type=str)
                    + NL()
                )
            )
        )

        def __init__(self, **kargs):
            for key, value in kargs.items():
                setattr(self, key, value)

        def _map_label_to_identifier(self, label):
            return label.replace("-", "_")

        def _map_identifier_to_label(self, attribute_name):
            return attribute_name.replace("_", "-")

    GlobalSettings.check_consumption = False

    describe_test("Test GET NetworkInterface")
    interface = get(BlankLine() + NetworkInterface, INPUT)
    # Do some spot checks of our extracted object.
    assert_equal(interface._meta_data.singleton_meta_data.label, "eth0-home")
    assert_equal(interface.address_family, "inet")
    assert_equal(interface.method, "static")
    assert_equal(interface.dns_nameservers, "67.207.128.4 67.207.128.5")
    assert_equal(interface.up, "flush-mail")

    describe_test("Test PUT NetworkInterface")
    interface.cheese_type = "cheshire"
    interface.address = "bananas"
    output = put(interface)

    expected = """\
iface eth0-home inet static
   netmask 255.255.255.0
   gateway  67.207.128.1
   dns-nameservers 67.207.128.4 67.207.128.5
   up flush-mail
   address bananas
   cheese-type cheshire
"""

    assert output == expected

    # Try creating from scratch.
    interface = NetworkInterface(
        address_family="inet",
        method="static",
        dns_nameservers="1.2.3.4 1.2.3.5",
        netmask="255.255.255.0",
    )
    output = put(interface, label="wlan3")
    expected = """\
iface wlan3 inet static
   dns-nameservers 1.2.3.4 1.2.3.5
   netmask 255.255.255.0
"""
    assert output == expected

    #
    # Now let's create a class to represent the whole configuration.
    #

    class InterfaceConfiguration(LensObject):
        auto_lens = Group(
            "auto"
            + WS(" ")
            + List(Keyword(additional_chars="_-", type=str), WS(" "), type=None)
            + WS("")
            + NL(),
            type=list,
            name="auto_lens",
        )
        __lens__ = ZeroOrMore(
            NetworkInterface | auto_lens | HashComment() | BlankLine()
        )

        interfaces = Container(store_items_of_type=[NetworkInterface], type=dict)
        auto_interfaces = Container(store_items_from_lenses=[auto_lens], type=list)

    if True:
        describe_test("GET InterfaceConfiguration")
        config = get(InterfaceConfiguration, INPUT)
        assert_equal(config.interfaces["eth0-home"].address, "192.168.1.1")
        assert_equal(config.auto_interfaces[0][1], "eth0")
        assert_equal(len(config.auto_interfaces), 2)

        describe_test("PUT InterfaceConfiguration")
        config.interfaces["eth0-home"].netmask = "bananas"
        config.auto_interfaces[0].insert(1, "wlan2")
        output = put(config)
        assert_equal(
            output,
            """
iface eth0-home inet static
   address 192.168.1.1
   gateway  67.207.128.1
   dns-nameservers 67.207.128.4 67.207.128.5
   up flush-mail
   netmask bananas

auto lo wlan2 eth0
# A comment
auto eth1 
""",
        )

    describe_test("CREATE InterfaceConfiguration")
    GlobalSettings.check_consumption = True
    interface = NetworkInterface(
        address_family="inet",
        method="static",
        dns_nameservers="1.2.3.4 1.2.3.5",
        netmask="255.255.255.0",
    )
    interface.some_thing = "something or another"
    config = InterfaceConfiguration()
    config.interfaces = {"eth3": interface}
    config.auto_interfaces = [["eth0"], ["wlan2", "eth2"]]

    output = put(config)
    expected = """iface eth3 inet static
   dns-nameservers 1.2.3.4 1.2.3.5
   netmask 255.255.255.0
   some-thing something or another
auto eth0
auto wlan2 eth2
"""
    assert output == expected


def test_init():
    """
    Just a few tests to figure out how we can use __new__ in object creation.
    """
    # What we want:
    #  Want to create an object with initial state regardless of constructor
    #  args.

    class Person:
        age = 10

        def __new__(cls, *args, **kargs):
            # It seems to me the args are passed only to allow customisation based
            # on them, since they are then passed to __init__ following this call in
            # typical creation.

            # Create the instance, also passing args - since may also be used for
            # customisation.
            self = super().__new__(cls)
            # Initialise some variables.
            self.name = None
            self.surname = None
            self.age = 3

            # Return the instance.
            return self

        def __init__(self, name, surname):
            d("Constructor called")
            self.name, self.surname = name, surname

        def __str__(self):
            return f"[{self.name}, {self.surname}]"

    person = Person("john", "smith")
    assert person.name == "john" and person.surname == "smith"
    person = Person.__new__(Person)
    assert person.name == None and person.surname == None

    # So it seems python falls back on class var if obj var of same name not found.
    d(person.__class__.__dict__)
    d(person.age)
    d(person.__class__.age)
