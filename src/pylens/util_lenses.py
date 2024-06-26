# Copyright (c) 2010-2011, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from pylens.base_lenses import And, AnyOf, Empty, Group, Lens, Or, Repeat
from pylens.charsets import alphanums, alphas
from pylens.core_lenses import Until
from pylens.debug import assert_msg
from pylens.exceptions import LensException
from pylens.util import has_value


class OneOrMore(Repeat):
    def __init__(self, *args, **options):
        if "min_count" not in options:
            options["min_count"] = 1
        # Mental note: Don't accidentally write something like super(Repeat...
        super().__init__(*args, **options)


OM = OneOrMore


class ZeroOrMore(Repeat):
    def __init__(self, *args, **options):
        if "min_count" not in options:
            options["min_count"] = 0
        super().__init__(*args, **options)


ZM = ZeroOrMore


class Optional(Or):
    def __init__(self, lens, **options):
        super().__init__(lens, Empty(), **options)


O = Optional  # noqa: E741


class List(And):
    """Shortcut lens for delimited lists."""

    def __init__(self, lens, delimiter_lens, **options):
        super().__init__(lens, ZeroOrMore(And(delimiter_lens, lens)), **options)


class NewLine(Or):
    """Matches a newline char or the end of text, so extends the Or lens."""

    def __init__(self, **options):
        super().__init__("\n", Empty(mode=Empty.END_OF_TEXT), **options)

    # TODO: Ensure it puts a \n regardless of being at end of file, to allow
    # appending. Could hook put


NL = NewLine  # Abbreviation


class Word(And):
    """
    Useful for handling keywords of a specific char range.
    """

    def __init__(
        self,
        body_chars,
        init_chars=None,
        min_count=1,
        max_count=None,
        negate=False,
        **options
    ):
        assert_msg(min_count > 0, "min_count should be more than zero.")

        # For convenience, enable type if label or is_label is set on this lens.
        if "is_label" in options or "label" in options:
            options["type"] = str

        if "type" in options and has_value(options["type"]):
            assert_msg(options["type"] == str, "If set the type of Word should be str.")
            any_of_type = str
            # Ensure the And type is list
            options["type"] = list
        else:
            any_of_type = None

        # Ensure chars are combined if this is a STORE lens.
        options["combine_chars"] = True

        left_lens = AnyOf(init_chars or body_chars, type=any_of_type)
        right_lens = Repeat(
            AnyOf(body_chars, type=any_of_type),
            min_count=min_count - 1,
            max_count=max_count and max_count - 1 or None,
        )

        super().__init__(left_lens, right_lens, **options)


class Whitespace(Or):
    """
    Whitespace helper lens, that knows how to handle (logically) continued lines with '\\n'
    or that preclude an indent which are useful for certain config files.
    """

    def __init__(
        self,
        default=" ",
        optional=False,
        space_chars=" \t",
        slash_continuation=False,
        indent_continuation=False,
        **options
    ):
        # Ensure default gets passed up to parent class - we use default to
        # determine if this lens is optional

        if "type" in options and has_value(options["type"]):
            # XXX: Could adapt this for storing spaces, though to be useful would need
            # to construct in such a way as to combine chars.
            assert_msg(False, "This lens cannot be used as a STORE lens")

        # XXX: This could be used later when we wish to make this a STORE lens.
        word_type = None

        # TODO: Could also use default to switch on, say, indent_continuation.

        # Set-up a lens the literally matches space.
        spaces = Word(space_chars, type=word_type, name="spaces")

        or_lenses = []

        # Optionally, augment with a slash continuation lens.
        if slash_continuation:
            or_lenses.append(Optional(spaces) + "\\\n" + Optional(spaces))

        # Optionally, augment with a indent continuation lens.
        if indent_continuation:
            or_lenses.append(Optional(spaces) + "\n" + spaces)

        # Lastly, add the straighforward spaces lens - since otherwise this would match before the others.
        or_lenses.append(spaces)

        # If the user set the default as the empty space, the Empty must also be a valid lens.
        if default == "" or optional:
            or_lenses.append(Empty())

        # Set up options for Or.
        options["default"] = default
        super().__init__(*or_lenses, **options)


WS = Whitespace  # Abreviation.


class NullLens(Lens):
    """
    When writing new lenses, particularly in a top-down fashion, this lens is
    useful for filling in lens branches that are yet to be completed.
    """

    def _get(self, concrete_input_reader):
        raise LensException(
            "NullLens always fails, and is useful as a filler for the incremental writing of lenses."
        )

    def _put(self, abstract_token, concrete_input_reader):
        raise LensException(
            "NullLens always fails, and is useful as a filler for the incremental writing of lenses."
        )

    # He, he. I won't test this one.


class KeyValue(Group):
    """
    Simply sets up the Group as an auto_list, which is useful when we just wish
    to store a value by a key.
    """

    def __init__(self, *args, **options):
        if "type" not in options:
            options["type"] = list
        if "auto_list" not in options:
            options["auto_list"] = True
        super().__init__(*args, **options)


class BlankLine(And):
    """
    Matches a blank line (i.e. optional whitespace followed by NewLine().
    """

    def __init__(self, **options):
        super().__init__(WS(""), NewLine(), **options)


class Keyword(Word):
    """
    A lens for matching a typical keyword.
    """

    def __init__(self, additional_chars="_", **options):
        super().__init__(
            alphanums + additional_chars,
            init_chars=alphas + additional_chars,
            **options
        )


class AutoGroup(Group):
    """
    Sometimes it may be convenient to not explicitly set a type on an outer lens
    in order to extract one or more items from sub-lenses, so this lens allows an
    outer container to be set automatically, using auto_list such that a single
    item may be passed through the lens.  If the enclosed lens has a type, then
    this lens simply becomes a transparent wrapper.
    """

    def __init__(self, lens, **options):
        """Note, this replaces __init__ of Group, which checks for a type."""
        if not lens.has_type():
            options["type"] = list
            options["auto_list"] = True
        super(Group, self).__init__(**options)
        self.extend_sublenses([lens])


class HashComment(And):
    """A common hash comment."""

    def __init__(self, **options):
        super().__init__("#", Until(NewLine()), NewLine(), **options)
