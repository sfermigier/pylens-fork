# Copyright (c) 2010-2011, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from pylens import get, put
from pylens.base_lenses import Group, Literal, Repeat
from pylens.charsets import alphanums, alphas
from pylens.containers import SOURCE, Container, LensObject
from pylens.core_lenses import Until
from pylens.debug import d  # Like print(...)
from pylens.debug import assert_equal, auto_name_lenses, describe_test
from pylens.settings import GlobalSettings
from pylens.util_lenses import (
    NL,
    WS,
    BlankLine,
    HashComment,
    KeyValue,
    Keyword,
    List,
    NewLine,
    Optional,
    Word,
    ZeroOrMore,
)

DEB_CTRL = """\
Source: libconfig-model-perl
Section: perl
Maintainer: Debian Perl Group <pkg-perl-maintainers@xx>
Build-Depends: debhelper (>= 7.0.0),
               perl-modules (>= 5.10) | libmodule-build-perl
Build-Depends-Indep: perl (>= 5.8.8-12), libcarp-assert-more-perl,
                     libconfig-tiny-perl, libexception-class-perl,
                     libparse-recdescent-perl (>= 1.90.0),
                     liblog-log4perl-perl (>= 1.11)
"""


def test_debctrl():
    """An example based on an example from the Augeas user guide."""

    # As a whole, this is a fairly complex lens, though as you work through it, you
    # should see that the steps are fairly consistent.
    # This lens demonstrates the use of labels and the auto_list lens modifier. I
    # also use incremental testing throughout, which should help you to follow
    # it.

    # We build up the lens starting with the easier parts, testing snippets as we go.
    # Recall, when we set is_label we imply the lens has type=str (i.e is a STORE
    # lens)
    simple_entry_label = (
        Literal("Source", is_label=True)
        | Literal("Section", is_label=True)
        | Literal("Maintainer", is_label=True)
    )

    #
    # Some general lenses for non-store artifacts of the string structure.
    #
    colon = WS("") + ":" + WS(" ", optional=True)
    comma_sep = (
        WS("", indent_continuation=True) + "," + WS("\n  ", indent_continuation=True)
    )
    option_sep = (
        WS(" ", indent_continuation=True, optional=True)
        + "|"
        + WS(" ", indent_continuation=True, optional=True)
    )

    #
    # simple_entry lens
    #

    # We lazily use the Until lens here, but you could parse the value further if you liked.
    # Note, auto_list unwraps a list if there is a single item, for convenience.
    # It is useful when we wish to associate a single item with a labelled
    # group.
    simple_entry = Group(
        simple_entry_label + colon + Until(NewLine(), type=str) + NewLine(),
        type=list,
        auto_list=True,
    )

    # Test the simple_entry lens
    got = simple_entry.get("Maintainer: Debian Perl Group <pkg-perl-maintainers@xx>\n")

    # Just to highlight the effect of auto_list on a list type lens.
    if simple_entry.options.auto_list:
        assert got == "Debian Perl Group <pkg-perl-maintainers@xx>"
    else:
        assert got == ["Debian Perl Group <pkg-perl-maintainers@xx>"]

    # An insight into how pylens stores metadata on items to assist storage.
    assert_equal(got._meta_data.label, "Maintainer")

    # Now try to PUT with the lens.
    # Notice how, since we are creating a new item with the lens, we must pass a
    # label to the lens, which is considered out-of-band of the item (i.e. it is
    # meta data).
    assert_equal(simple_entry.put("some value", label="Source"), "Source: some value\n")

    #
    # depends_entry lens
    #

    # Note the order of these: longest match first, since they share a prefix.
    depends_entry_label = Literal("Build-Depends-Indep", is_label=True) | Literal(
        "Build-Depends", is_label=True
    )

    # Here is an interesting lens, so let me explain it.
    # Each dependancy may be either a single application or a list of alternative
    # applications (separated by a '|'), so we use an List lens and set it as an
    # auto_list.
    # Since the application may have an optional version string, we store the application
    # info in a dict using labels for the app name and version string.
    package_options = List(
        Group(
            Word(alphanums + "-", init_chars=alphas, label="name")
            + Optional(WS(" ") + "(" + Until(")", label="version") + ")"),
            type=dict,
        ),
        option_sep,
        auto_list=True,
        type=list,
    )

    got = package_options.get("perl-modules (>= 5.10) | libmodule-build-perl")
    expected = [
        {"name": "perl-modules", "version": ">= 5.10"},
        {"name": "libmodule-build-perl"},
    ]
    assert got == expected

    # Then test auto_list ensures the list is unwrapped for a single item.
    assert_equal(
        package_options.get("perl-modules (>= 5.10)"),
        {"name": "perl-modules", "version": ">= 5.10"},
    )

    assert_equal(
        package_options.put({"version": "3.4", "name": "some-app"}), "some-app (3.4)"
    )
    assert_equal(
        package_options.put(
            [
                {"version": "3.4", "name": "some-app"},
                {"version": "< 1.2", "name": "another-app"},
            ]
        ),
        "some-app (3.4) | another-app (< 1.2)",
    )

    # Now we wrap the package options in a comma separated list.  Notice how we do
    # not set the type to list, since we wish these items to be stored in a higher
    # level list, to avoid excessive list nesting.
    depends_list = List(package_options, comma_sep)

    # It might be over the top, but let's make sure this part works too.
    # Note that, for the isolated test of this lens we must set a type on it,
    # otherwise the sub-lenses will have nothing in which to store their extracted
    # items.
    depends_list.type = list
    got = depends_list.get(
        """debhelper (>= 7.0.0) | cheese,\n \t  perl-modules (>= 5.10) , libmodule-build-perl | monkey (1.2)"""
    )
    expected = [
        [{"name": "debhelper", "version": ">= 7.0.0"}, {"name": "cheese"}],
        {
            "name": "perl-modules",
            "version": ">= 5.10",
        },  # Not in list due to auto_list.
        [{"name": "libmodule-build-perl"}, {"name": "monkey", "version": "1.2"}],
    ]
    assert got == expected

    # Now lets try to PUT (actually CREATE a new) our abstract structure into a string.
    output = depends_list.put(
        [
            [
                {"name": "beans", "version": ">= 1.2"},
                {"name": "eggs"},
                {"name": "spam", "version": "<= 2.4"},
            ],
            {"name": "cheese", "version": "3.3"},
        ]
    )
    assert_equal(output, "beans (>= 1.2) | eggs | spam (<= 2.4),\n  cheese (3.3)")

    # Remember to remove the type now that it has been tested in isolation.
    depends_list.type = None

    # Now put the dependancy entry togather.
    depends_entry = Group(
        depends_entry_label + colon + depends_list + WS("") + NewLine(), type=list
    )

    # And now we have our final lens.
    lens = Repeat(simple_entry | depends_entry, type=dict, alignment=SOURCE)

    # This names all the lenses based on their variable names, to improve clarity of debug logs.
    auto_name_lenses(locals())

    # Now lets get the config file snippet as an abstract form we can easily
    # manipulate.
    got = lens.get(DEB_CTRL)

    # Now let's modify it a bit
    del got["Build-Depends"]

    # Lets insert some more dependancies.
    got["Build-Depends-Indep"].insert(
        2, [{"name": "cheese", "version": "3.3"}, {"name": "spam"}]
    )
    output = lens.put(got)

    # Now lets check the output.
    expected = """\
Source: libconfig-model-perl
Section: perl
Maintainer: Debian Perl Group <pkg-perl-maintainers@xx>
Build-Depends-Indep: perl (>= 5.8.8-12), libcarp-assert-more-perl,
                     cheese (3.3) | spam, libconfig-tiny-perl,
                     libexception-class-perl,
                     libparse-recdescent-perl (>= 1.90.0),
  liblog-log4perl-perl (>= 1.11)
"""
    assert output == expected

    # Now let's finish off by creating some output from scratch (i.e. using
    # default values of all non-store lenses rather than any original input.
    data = {
        "Source": "Just a simple entry",
        "Build-Depends-Indep": [
            [{"name": "cheese", "version": "1.2"}, {"name": "nbdebug"}],
            {"name": "someapp", "version": "<= 1.1"},
        ],
    }
    output = lens.put(data)
    expected = """Source: Just a simple entry\nBuild-Depends-Indep: cheese (1.2) | nbdebug,\n  someapp (<= 1.1)\n"""
    assert output == expected
