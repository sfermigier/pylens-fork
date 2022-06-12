#
# Copyright (c) 2010-2011, Nick Blundell
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Nick Blundell nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Author: Nick Blundell <blundeln [AT] gmail [DOT] com>
# Organisation: www.nickblundell.org.uk
#
#

"""
These lenses form the core of pylens.  The Lens class is the base of all other
lenses and encapsulates (and hides) much of the complexity of the framework
whilst allowed us to extend it.
"""
import inspect

from .containers import AbstractContainer, ContainerFactory, LensObject
from .debug import IN_DEBUG_MODE, assert_msg, d
from .exceptions import (
    EndOfStringException,
    LensException,
    NoDefaultException,
    NotFullyConsumedException,
    TooFewIterationsException,
)
from .item import enable_meta_data, list_wrapper
from .readers import ConcreteInputReader
from .rollback import Rollbackable, automatic_rollback, get_rollbackables_state
from .settings import GlobalSettings
from .util import Properties, escape_for_display, has_value, range_truncate, truncate

#########################################################
# Base Lens
#########################################################


class Lens:
    """Base lens, which all other lenses extend."""

    def __init__(self, type=None, name=None, default=None, **options):
        """
        Arguments:

          - type: The native type of this lens (e.g. int, str, some LensObject
            class).  If set, this is a STORE lens, otherwise a NON-STORE lens.
          - name: For assigning a name to this lens for debugging purposes.
          - default: the default output of this lens if a NON-STORE lens.
          - options: arbitrary keyword options can be set on a lens to affect its
            functionality in an extendible way.  For example, we might use this to
            specify how we align data items to their original position in the
            source string, perhaps by some label, their original position, or by
            some order in the native type.
        """
        self.type = type

        # Set the default value of this lens (in the PUT direction) if it is not a
        # STORE lens.
        if has_value(type) and has_value(default):
            raise Exception(
                "Cannot set a default value on a lens with a type (i.e. on a store lens)."
            )
        self.default = default

        # For debugging purposes, allow a friendly name to be given to the lens,
        # otherwise an automated name will be displayed (e.g. "And(106)")
        self.name = name

        # Composite lenses will store their sub-lenses in here, for consistency,
        # and later perhaps to allow for some reasonning about a lens' structure.
        self.lenses = []

        # Allow arbitrary arguments to be set on the lens which can aid flexible
        # storage and retrival of items from a container.
        self.options = Properties(**options)

        #
        # Argument shortcuts
        #

        # There is no point setting a non-store lens as a label or to have a
        # label, so assume the user wanted a lens type of str.
        if not has_value(self.type) and (self.options.is_label or self.options.label):
            self.type = str

    def get(self, concrete_input, current_container=None):
        """
        Returns a data item from the string *concrete_input* according to this
        lens and its type; if this lens has no type, the input string is simply
        consumed and nothing returned to be used in our abstract structure.

        This effectively wraps the _get function (GET proper) of the specific
        lens, handling all of the common tasks (e.g. input normalisation, creation
        of stateful item containers, rolling back state for failed parsing
        branches, etc.).

        Arguments:

          - concrete_input: Concrete input string to parse from.
          - current_container: Outer container (e.g. a list, dict, some LensObject
            class, etc.) into which items are being extracted.  Usually this is
            used only internally, as the parsing descends into sub-lenses, some of which
            define their own containers (e.g. using lenses such as Group) and some which
            don't but instead store items into some higher-level container.
        """
        #
        # Algorithm
        #
        # If we have a container type
        #   replace container with new one - to save hassle of doing it in each
        #   _get (proper), since a typed-container lens will always deal with its
        #   own container
        # item = _get(input, container)
        # if typed_lens:
        #   cast item if not instance
        #   assert(item is correct type)
        #   assert not already got properties
        #   set properties
        #
        # Note, even if non-typed, we may return an item from a lens we wrap (e.g. Or)
        #
        # item = process_item(item) # e.g. allow pre-processing of item (e.g. for auto_list)
        #
        # return item

        # Ensure we have the concrete input in the form of a ConcreteInputReader
        assert_msg(has_value(concrete_input), "Cannot GET if there is no input string!")
        concrete_input_reader = self._normalise_concrete_input(concrete_input)

        if IN_DEBUG_MODE:
            d(f"Initial state: in={concrete_input_reader}, cont={current_container}")

        # Remember the start position of the concrete reader, to aid
        # re-alignment of concrete structures when we Lens.put is later called.
        # We will store this in a returned items meta_data, effictively giving it
        # a lifeline back to where it came from.
        concrete_start_position = concrete_input_reader.get_pos()

        # Create an empty appropriate container class for our lens, if there is one;
        # this will be None if we are not a container-type lens (e.g. a dict or
        # list).
        lens_container = self._create_lens_container()
        if lens_container:
            d("Created container")

        # If we are a container-type lens, replace the current container of
        # sub-lenses with our own container (lens_container).
        if lens_container:
            # Call GET proper with our container, checking that no item is returned,
            # since all items should be stored WITHIN the container
            assert_msg(
                self._get(concrete_input_reader, lens_container) == None,
                f"Container lens {self} has GOT an item, but all items must be stored in the current container, not returned.",
            )

            # Since we created the container, we will return it as our item, for a
            # higher order lens to store.
            item = lens_container.unwrap()

        # Otherwise, call GET proper using the outer container, if there is one.
        else:
            item = self._get(concrete_input_reader, current_container)

        # If we are a STORE lens (i.e. we extract an item) ...
        if self.has_type():

            # Cast the item to our type (usually if it is a string being cast to a
            # simple type, such as int).
            assert_msg(
                has_value(item),
                f"Somethings gone wrong: {self} is a STORE lens, so we should have got an item.",
            )
            if not isinstance(item, self.type):
                item = self.type(item)

            # Double check we got an item of the correct type (after any casting).
            assert isinstance(item, self.type)

            # Allow meta data to be stored on the item.
            item = enable_meta_data(item)

            # Now add source info to the item's meta data, which will help when
            # putting it back into a concrete structure.

            # A reference to the lens that extracted the item.
            item._meta_data.lens = self
            d(f"Set meta on {item} to {item._meta_data}")

            # A reference to the concrete reader and position parsed from.
            item._meta_data.concrete_start_position = concrete_start_position
            item._meta_data.concrete_end_position = concrete_input_reader.get_pos()
            item._meta_data.concrete_input_reader = concrete_input_reader

            # If the item was unwrapped from a container, update meta with label
            # from the container, which may have been set if there was an is_label
            # lens.
            if lens_container:
                item._meta_data.label = lens_container.get_label()

        # Note that, even if we are not a typed lens, we may return an item
        # extracted from some sub-lens, the Or lens being a good example.

        if IN_DEBUG_MODE:
            if has_value(item):
                d(
                    "GOT: %s %s"
                    % (
                        item,
                        item._meta_data.label
                        and "[label: '%s']" % (item._meta_data.label)
                        or "",
                    )
                )
            else:
                d("GOT: NOTHING (to store)")

        # If appropriate, check the input was fully consumed by this lens
        if (
            isinstance(concrete_input, str)
            and GlobalSettings.check_consumption
            and not concrete_input_reader.is_fully_consumed()
        ):
            raise NotFullyConsumedException(
                f"The following input remains to be consumed by this lens: '{concrete_input_reader.get_remaining()}'"
            )

        # Pre-process outgoing item.
        item = self._process_outgoing_item(item)

        return item

    def put(self, item=None, concrete_input=None, current_container=None, label=None):
        """
        Puts an item from our abstract model through the lens to generate its
        string representation, weaving the model items back into an original
        string if there was one (i.e. if we are PUTTING rather than CREATING).

        Frankly, this is the big beast that drives pylens and you should not worry
        too much about understanding the internals if you simply wish to build lenses.

        Arguments:

          - item: - item to PUT.
          - concrete_input: concrete input for weaving between STORE lens values.
          - current_container - outer container from which items will be consumed
            and PUT back.
          - label - allows the user to set a label on the passed item, to allow for
            structures that internally contain a label.

        This effectively wraps the _put function (PUT proper) of the specific
        lens, handling all of the common tasks (e.g. input normalisation, creation
        of stateful containers, rolling back state for failed parsing branches).

        Note that we make no distinction between PUT and CREATE (from the
        literatur): since a previously extracted item will carry information of
        its concrete structure within its meta data it will use this for weaving
        in non-stored artifacts; otherwise, default artifacts will be used (as in
        CREATE).

        In some cases the order that items are put back in will differ from their
        original order, so we are careful to both consume and discard from the
        outer concrete structure whilst PUTTING with the item' own concrete
        structure.  If both structures are aligned (i.e. the item goes back in its
        original order) then a single PUT on the outer concrete reader is
        performed.
        """

        #
        # Algorithm
        #
        # Assert item => container == None
        # Note, though an item will hold its own input, the lens must consumed from
        # the outer input reader if one is supplied.
        #
        # Normalise concrete input reader.
        #
        # If we are an un-typed lens
        #   if we have a default value and no concrete input, return it.
        #   otherwise return put proper, passing through our args - note, item could be passed through us
        #
        # Now assume we are typed lens
        #
        #  If we are passed an item
        #    ensure meta enabled (e.g. for a new item, not previously extracted)
        #    pre-process item (e.g. to handle auto_list)
        #    check correct type, else raise LensException
        #    get the item input reader if there is one - can be None
        #    if item_input_reader
        #      if input_reader
        #        if item_input_reader is not aligned with (outer) input_reader
        #          consume from input_reader
        #          set input_reader item_input_reader
        #        else we use the input_reader (i.e both consume and put) - can discard item_input_reader
        #    else :
        #      No input for this item, so we are CREATING
        #      if input_reader
        #        consume from input_reader
        #      set input_reader = None
        #
        #    if we are container type, wrap item as current_container and set item = None
        #    call put proper on item with item, input_reader and current_container
        #  else if we are passed a container (and no item)
        #    instruct the container to put it.
        #
        #  Should have returned by here, so raise LensException: expected something to put.
        #

        # If we are passed an item, we do not expect an outer container to also have
        # been passed.
        if has_value(item):
            assert_msg(
                current_container == None,
                "A lens should not be passed both a container and an item.",
            )
            # Note, however, that a typed item may well be passed an outer concrete
            # reader, which will be used for weaving in non-stored artifacts of concrete
            # structures.

        # Ensure we have a ConcreteInputReader; otherwise None.
        concrete_input_reader = self._normalise_concrete_input(concrete_input)

        # We need this for checking consumption, since concrete_input_reader can be
        # changed by our algorithm.
        original_concrete_input_reader = concrete_input_reader

        # Display some useful info for debug tracing.
        if IN_DEBUG_MODE:

            # It's very useful to see if an item holds a label in its meta.
            if hasattr(item, "_meta_data") and has_value(item._meta_data.label):
                item_label_string = f" [label: {item._meta_data.label}]"
            else:
                item_label_string = ""

            d(
                f"Initial state: item={item}{item_label_string}, in={concrete_input_reader}, cont={current_container}"
            )

        # First handle cases where our lens does not directly store an item: it will
        # either return the default output string, if it has one; or it will
        # generate some output internally, perhaps from the input or from the
        # default output of a sub-lens.
        if not self.has_type():
            # Use default (for CREATE)
            if concrete_input_reader == None and has_value(self.default):
                output = str(self.default)

            # Otherwise do a PUT proper, passing through our arguments, for example
            # our child lens may put an item directly or from the container of use
            # its own default value.
            else:
                output = self._put(item, concrete_input_reader, current_container)

        # Now we can assume that our lens has a type (i.e. will directly PUT an
        # item)
        elif has_value(item):

            # For the sake of algorithmic consistancy, ensure the incoming item can
            # hold meta data.
            item = enable_meta_data(item)

            # Store original state of item, including meta data, so we can recover it on success,
            # since PUT can be destructive to some containers, depending on how they
            # are implemented and their meta data.
            original_meta_data = item._meta_data.copy()
            original_item = item
            if isinstance(item, Rollbackable):
                original_state = item._get_state()

            # Associate a label with the item, usually a label passed from the user,
            # which is required internally by a structure.
            if has_value(label):
                item._meta_data.label = label

            # Pre-process the incoming item (e.g to handle auto_list or other future
            # extensions)
            item = self._process_incoming_item(item)

            # Check our item's type is compatible with the lens.
            if not isinstance(item, self.type):
                raise LensException(
                    "This lens %s of type %s cannot PUT an item of that type %s"
                    % (self, self.type, type(item))
                )

            # If this item was previously GOTten, we can get its original input.
            if has_value(item._meta_data.concrete_input_reader):

                # Create a personal concrete reader for this item, based on its meta
                # data.
                item_input_reader = ConcreteInputReader(
                    item._meta_data.concrete_input_reader
                )
                item_input_reader.set_pos(item._meta_data.concrete_start_position)

                # If the readers are not aligned...
                if not (
                    has_value(concrete_input_reader)
                    and item_input_reader.is_aligned_with(concrete_input_reader)
                ):
                    # Consumed from the outer reader, if there is one.
                    if has_value(concrete_input_reader):
                        d(
                            "Inputs not aligned, so consuming and discarding from outer input reader."
                        )
                        self.get_and_discard(concrete_input_reader, current_container)

                    # Now use substitute the outer reader (if there was one) with our
                    # item's reader
                    concrete_input_reader = item_input_reader

            else:

                # Otherwise, if our item had no source meta, we will be CREATING, but
                # must still consume from the outer reader, if there is one.
                if has_value(concrete_input_reader):
                    d(
                        "Inputs not aligned, so consuming and discarding from outer input reader."
                    )
                    self.get_and_discard(concrete_input_reader, current_container)

                concrete_input_reader = None

            # Now, the item could be a container (e.g. a list, dict, or some other
            # AbstractContainer), so to save the _put definition from having to wrap
            # it for stateful consumption of items, let's do it here.

            # TODO: We need to check that the container, if from an item, has been fully consumed
            # here and raise an LensException if it has not.
            item_as_container = ContainerFactory.wrap_container(item)
            if has_value(item_as_container):
                # The item is now represented as a consumable container.
                item = None
                current_container = item_as_container
                # Set the us as the lens of this container, which it will use to determine alignment mode, etc.
                current_container.set_container_lens(self)
            else:
                # When PUTing a non-container item, for consistancy, should cast to string (e.g. if int
                # passed) and discard current container from this branch.
                item = str(item)
                current_container = None

            # Now that arguments are set up, call PUT proper on our lens.
            try:
                output = self._put(item, concrete_input_reader, current_container)

                # Check the container items have been fully consumed by this lens.
                if (
                    has_value(item_as_container)
                    and GlobalSettings.check_consumption
                    and not current_container.is_fully_consumed()
                ):
                    raise NotFullyConsumedException(
                        "The container %s has not been fully consumed."
                        % current_container
                    )
            finally:
                # Now recover the original state of the item, including its meta data,
                # whether put succeeded or not.
                original_item._meta_data = original_meta_data
                if isinstance(original_item, Rollbackable):
                    original_item._set_state(original_state)

        # If instead of an item we have a container, instruct the container to put
        # an item into the lens.  This gives the container much flexibilty about
        # how it chooses an item to PUT, perhaps even doing so tentatively.
        elif has_value(current_container):
            assert isinstance(current_container, AbstractContainer)
            output = current_container.consume_and_put_item(self, concrete_input_reader)

        # Catch-all case.  We should have been passed an item to PUT.
        else:
            raise LensException(
                "This typed lens expected to PUT an item either directly or from a container."
            )

        # Report what we PUT.
        if IN_DEBUG_MODE:
            if has_value(output):
                d(f"PUT: '{output}'")
            else:
                d("PUT: NOTHING")

        # If appropriate, check the input was fully consumed by this lens
        if (
            isinstance(concrete_input, str)
            and GlobalSettings.check_consumption
            and not original_concrete_input_reader.is_fully_consumed()
        ):
            raise NotFullyConsumedException(
                f"The following input remains to be consumed by this lens: '{original_concrete_input_reader.get_remaining()}'"
            )

        return output

    def get_and_discard(self, concrete_input, current_container):
        """
        Sometimes we wish to consume input but discard any items GOTten.
        Note, it is tempting to somehow not use the current_container, though some lenses might
        one day use the current container state, so we must first store items in the
        container before reverting it.  For example, the opening and closing tags in
        XML-like structures.
        """
        # If we have a container, store its start state.
        if has_value(current_container):
            container_start_state = current_container._get_state()

        # Issue the get.
        self.get(concrete_input, current_container)

        # Now revert the state.
        if has_value(current_container):
            current_container._set_state(container_start_state)

    def has_type(self):
        """Determines if this lens will GET and PUT a variable - a STORE lens."""
        return self.type != None

    def container_get(self, lens, concrete_input_reader, current_container):
        """
        Convenience function to handle the case where:
          - if there is a container, get and store an item into it
          - if there is no container, call get and check nothing is returned

        This simplifies lens such as And and Repeat, whose logic does not have to
        worry about whether or not it is acting as a STORE lens.
        """
        if has_value(current_container):
            current_container.get_and_store_item(lens, concrete_input_reader)
        else:
            # Call get on lens passing no container, checking it returns no item.
            assert_msg(
                lens.get(concrete_input_reader, None) == None,
                "The untyped container lens %s did not expect the sub-lens %s to return an item"
                % (self, lens),
            )

    def container_put(self, lens, concrete_input_reader, current_container):
        """Reciprocal of container_get."""
        if lens.has_type():
            assert_msg(
                has_value(current_container),
                "Lens %s expected an enclosing container from which to pluck an item."
                % lens,
            )
            return current_container.consume_and_put_item(lens, concrete_input_reader)
        else:
            # Otherwise, we pass through arguments (e.g. for non-store sublenses or
            # lens that enclose STORE lenses)
            return lens.put(None, concrete_input_reader, current_container)

    def set_sublens(self, sublens):
        """Used if only a single sublens is required (e.g. the Forward lens)."""
        self.lenses = [self._preprocess_lens(sublens)]

    def extend_sublenses(self, new_sublenses):
        """
        Adds new sublenses to this lens, being sure to preprocess them (e.g. convert
        strings to Literal lenses, etc.).
        """
        for new_sublens in new_sublenses:
            self.lenses.append(self._preprocess_lens(new_sublens))

    #
    # Helper methods.
    #

    def _normalise_concrete_input(self, concrete_input):
        """If a string is passed, ensure it is normalised to a ConcreteInputReader."""
        if not has_value(concrete_input):
            return None

        if isinstance(concrete_input, str):
            concrete_input = ConcreteInputReader(concrete_input)

        assert_msg(
            isinstance(concrete_input, ConcreteInputReader),
            f"Expected to have a ConcreteInputReader not a {type(concrete_input)}",
        )
        return concrete_input

    def _create_lens_container(self):
        """Creates a container for this lens, if the lens is of a container type."""
        return ContainerFactory.create_container(self.type)

    # XXX: I don't really like these forward declarations, but for now this does
    # the job.  Perhaps lenses can be registered with the framework for more
    # flexible coercion.
    @staticmethod
    def _coerce_to_lens(lens_operand):
        """
        Intelligently converts a type to a lens (e.g. string instance to a Literal
        lens) to ease lens definition; or a class or instance.
        """
        # Coerce string to Literal
        if isinstance(lens_operand, str):
            lens_operand = Literal(lens_operand)

        # Coerce LensObject class to its internally defined lens, such that the lens will GET
        # and PUT instances of that class.
        elif inspect.isclass(lens_operand) and issubclass(lens_operand, LensObject):
            assert_msg(
                hasattr(lens_operand, "__lens__"),
                f"LensObject {lens_operand} defines no __lens__ variable",
            )
            # Note, we also coerce __lens__ to a lens, just for completeness (e.g. if
            # lens was simply a string, it would be coerced to a Literal lens.
            lens_operand = Group(
                Lens._coerce_to_lens(lens_operand.__lens__), type=lens_operand
            )

        assert_msg(
            isinstance(lens_operand, Lens),
            f"Unable to coerce {lens_operand} to a lens",
        )
        return lens_operand

    def _preprocess_lens(self, lens):
        """
        Preprocesses a lens to enable type-to-lens conversion. This will be
        called before processing lens arguments.
        """
        lens = Lens._coerce_to_lens(lens)
        return lens

    #
    # Allow the potential modification of incoming and outgoing items (e.g. to
    # handle auto_list, where a single-item list is converted to and from a
    # single item)
    #

    def _process_outgoing_item(self, item):
        """
        Allows post-processing of an item in the GET direction.

        For example, to handle auto_list, where a single-item list is converted to
        a single item.
        """

        # This allows a list singleton to be returned as a single item, for
        # convenience.
        if (
            self.options.auto_list is True
            and self.has_type()
            and issubclass(self.type, list)
            and len(item) == 1
        ):
            # The easy part is extracting a singleton from the list, but we must
            # also preserve the source meta data of the list item by piggybacking it onto
            # the extracted item's meta data

            list_meta_data = item._meta_data
            singleton_meta_data = item[0]._meta_data
            item = item[0]
            item._meta_data = list_meta_data
            item._meta_data.singleton_meta_data = singleton_meta_data

        # This allows a list of chars to be combined into a string.
        elif (
            self.options.combine_chars
            and self.has_type()
            and issubclass(self.type, list)
        ):
            # Note, care should be taken to use this only when a list of single chars is used.
            # XXX: Note, we actually loose each char's meta data here, but this should not be a problem in most cases.
            original_meta = item._meta_data
            item = enable_meta_data("".join(item))
            item._meta_data = original_meta

        # Mark if this item is to be used AS a label.
        if self.options.is_label:
            item._meta_data.is_label = True
        # Mark the item to have a static label.
        elif has_value(self.options.label):
            item._meta_data.label = self.options.label

        return item

    def _process_incoming_item(self, item):
        """
        Pre-processes an item in the PUT direction.  We can assume we are a lens
        with a type when this is called.

        For example, reciprocating the auto_list example in
        _process_outgoing_item.
        """

        # TODO: What if item was GOTen from auto list but is not being put directly
        # - it will try to use the wrong source meta.

        # Handle auto_list, expanding an item into a list, being careful to restore any meta data.
        if (
            self.options.auto_list is True
            and issubclass(self.type, list)
            and not isinstance(item, list)
        ):

            # Create some variables to clarify the process.
            singleton = item
            list_meta_data = item._meta_data
            singleton_meta_data = item._meta_data.singleton_meta_data

            # Safeguard to ensure piggybacked data cannot be used more than once.
            list_meta_data.singleton_meta_data = None

            # Wrap the singleton in a list, giving it the meta_data of the item.
            item = list_wrapper([singleton])
            item._meta_data = list_meta_data

            # Ensure the singleton has its meta data restored, if it was maintained.
            if singleton_meta_data:
                singleton._meta_data = singleton_meta_data

        # This handles the case where we might have GOTten an item from an auto list
        # but are now putting it directly.  We simply reinstate the singleton meta
        # data on the item.
        elif has_value(item._meta_data.singleton_meta_data):
            item._meta_data = item._meta_data.singleton_meta_data

        # This allows a list of chars to be combined into a string.
        elif (
            isinstance(item, str)
            and self.options.combine_chars
            and issubclass(self.type, list)
        ):
            # Note, care should be taken to use this only when a list of single chars is used.
            original_meta = item._meta_data
            item = enable_meta_data(list(item))
            item._meta_data = original_meta

        return item

    #
    # Operator overloads to make for cleaner lens construction.
    #

    def __add__(self, other_lens):
        return And(self, self._preprocess_lens(other_lens))

    def __or__(self, other_lens):
        return Or(self, self._preprocess_lens(other_lens))

    # Reflected operators, so we can write: lens = "a string" + <some_lens>
    def __radd__(self, other_lens):
        return And(self._preprocess_lens(other_lens), self)

    def __ror__(self, other_lens):
        return Or(self._preprocess_lens(other_lens), self)

    #
    # Specialised lenses must override these to implement their GET and PUT
    # proper.
    #

    def _get(self, concrete_input_reader, current_container):
        """GET proper for a specific lens."""
        raise NotImplementedError("")

    def _put(self, item, concrete_input_reader, current_container):
        """
        PUT proper for a specific lens.

        Note, a low-level lens (i.e. that directly consumes input or tokens)
        should check if it has been mistakenly passed an item to PUT if it is not
        operating as a STORE lens (i.e. if the lens has no type).
        """
        raise NotImplementedError("")

    #
    # For debugging
    #

    def _display_id(self):
        """Useful for identifying specific lenses in debug traces."""
        # If we have a specic name, use it.
        if self.name:
            return self.name

        # If no name, a hash with small range gives us a reasonably easy way to
        # distinguish lenses in debug traces.
        return str(hash(self) % 256)

    # String representation.
    def __str__(self):
        # Bolt on the class name, to ease debugging.
        return f"{self.__class__.__name__}({self._display_id()})"

    __repr__ = __str__

    def __instance_name__(self):
        """Used by my nbdebug module to display a custom debug message context string."""
        return self.name or str(self)


#########################################################
# Core lenses - required fundamental lenses.
#########################################################


class And(Lens):
    """A lens that is formed from the ANDing of two sub-lenses."""

    def __init__(self, *lenses, **options):

        # Must always remember to invoke the parent lens, so it can initialise
        # common arguments.
        super().__init__(**options)

        # Flatten sub-lenses that are also Ands, so we don't have too much nesting,
        # which makes debugging lenses a nightmare.
        for lens in lenses:
            # Note, isinstance would be too vague - Word() was absorbed due to this.
            # Also, self.class == lens.__class__ still too vague -> Collapsed my nested lists!
            if lens.__class__ == And and self.__class__ == And:
                self.extend_sublenses(lens.lenses)
            else:
                self.extend_sublenses([lens])

    def _get(self, concrete_input_reader, current_container):
        """Sequential GET on each lens."""
        for lens in self.lenses:
            self.container_get(lens, concrete_input_reader, current_container)

        # Important: we should not return anything, since we work on the outer
        # container, that the Lens class sets up for us in Lens.get regardless if our
        # lens created the container or not.

    def _put(self, item, concrete_input_reader, current_container):
        """Sequential PUT on each lens."""
        # In the same way that we do not return an item in GET, we do not expect
        # to PUT an individual item; again, this is handle in Lens.put
        assert_msg(
            item == None,
            "Lens %s did not expect to PUT an individual item %s, since it PUTs from a container"
            % (self, item),
        )

        # Simply concatenate output from the sub-lenses.
        output = ""
        for lens in self.lenses:
            output += lens.put(None, concrete_input_reader, current_container)

        return output


class Or(Lens):
    """
    This is the OR of two lenses.
    """

    def __init__(self, *lenses, **options):
        super().__init__(**options)

        # Flatten sub-lenses that are also Ors, so we don't have too much nesting, which makes debugging lenses a nightmare.
        for lens in lenses:
            # Note, isinstance would be too vague - see my note in And.
            if lens.__class__ == Or and self.__class__ == Or:
                self.extend_sublenses(lens.lenses)
            else:
                self.extend_sublenses([lens])

    def _get(self, concrete_input_reader, current_container):
        """
        Calls get on each lens until the firstmost succeeds.

        Note that the lens should be designed accordingly to break ties over
        multiple valid paths.
        """
        for lens in self.lenses:
            try:
                with automatic_rollback(concrete_input_reader, current_container):
                    return lens.get(concrete_input_reader, current_container)
            except LensException:
                pass

        raise LensException("We should have GOT one of the lenses.")

    def _put(self, item, concrete_input_reader, current_container):
        """
        It is important to realise that here we can either do a:
          - straight PUT, where the lens both consumes input and PUTs an item
          - cross PUT, where one lens consumes input and another PUTS an item

        Also, it is useful to consider a lens l = A | Empty(), since if we first try
        straight PUT with each lens, the Empty lens will always succeed, possibly
        resulting in input not being consumed correctly by lens A.  This case
        influences my redesign of this algorithm.
        """

        # Algorithm
        #
        # For lens_a in lenses
        #   Try straight put with lens_a -> return if succeed
        #   lens_a.get_and_discard(input)
        #
        #   For lens_b in lenses, lens_b != lens_a
        #     lens.put(input=None)

        # Store the initial state.
        initial_state = get_rollbackables_state(
            concrete_input_reader, current_container
        )

        for lens_a in self.lenses:
            # Try a straight put on the lens - this will also succeed if there is no
            # input.
            try:
                with automatic_rollback(
                    concrete_input_reader,
                    current_container,
                    initial_state=initial_state,
                ):
                    return lens_a.put(item, concrete_input_reader, current_container)
            except LensException:
                pass

            # If we have a concrete_input_reader, we will next attempt a cross PUT.
            if not concrete_input_reader:
                continue

            # Try to consume input with the lens_a
            try:
                with automatic_rollback(
                    concrete_input_reader,
                    current_container,
                    initial_state=initial_state,
                ):
                    lens_a.get_and_discard(concrete_input_reader, current_container)
            except LensException:
                continue

            # If the GET suceeded with lens_a, try to PUT with one of the other
            # lenses.
            for lens_b in self.lenses:
                if lens_a is lens_b:
                    continue

                try:
                    with automatic_rollback(
                        concrete_input_reader,
                        current_container,
                        initial_state=initial_state,
                    ):
                        return lens_b.put(item, None, current_container)
                except LensException:
                    pass

        raise LensException("We should have PUT one of the lenses.")

    def _display_id(self):
        """For debugging clarity."""
        return " | ".join([str(lens) for lens in self.lenses])


class AnyOf(Lens):
    """
    The first useful low-level lens. Matches a single char within a specified
    set, and can also be negated.
    """

    def __init__(self, valid_chars, negate=False, **options):
        super().__init__(**options)
        self.valid_chars, self.negate = valid_chars, negate

    def _get(self, concrete_input_reader, current_container):
        """
        Consumes a valid char from the input, returning it if we are a STORE
        lens.
        """
        char = None
        try:
            char = concrete_input_reader.consume_char()
            if not self._is_valid_char(char):
                raise LensException(
                    f"Expected char {self._display_id()} but got '{truncate(char)}'"
                )
        except EndOfStringException:
            raise LensException(
                f"Expected char {self._display_id()} but at end of string"
            )

        if self.has_type():
            return char
        else:
            return None

    def _put(self, item, concrete_input_reader, current_container):
        """
        If a store lens, tries to output the given char; otherwise outputs
        original char from concrete input.
        """
        # If we are not a store lens, simply return what we would consume from the input.
        if not self.has_type():
            # We should not have been passed an item.
            assert not has_value(item)
            if has_value(concrete_input_reader):
                concrete_start_position = concrete_input_reader.get_pos()
                self._get(concrete_input_reader, current_container)
                return concrete_input_reader.get_consumed_string(
                    concrete_start_position
                )

            else:
                raise NoDefaultException(
                    "Cannot CREATE: a default should have been set on lens %s, or a higher lens."
                    % self
                )

        # If this is PUT (vs CREATE) then first consume input.
        if concrete_input_reader:
            self.get(concrete_input_reader)

        if not (isinstance(item, str) and len(item) == 1 and self._is_valid_char(item)):
            raise LensException(
                f"Invalid item '{item}', expected {self._display_id()}."
            )
        return item

    def _is_valid_char(self, char):
        """Tests if that passed is a valid character for this lens."""
        if self.negate:
            return char not in self.valid_chars
        else:
            return char in self.valid_chars

    def _display_id(self):
        """To aid debugging."""
        if self.name:
            return self.name
        if self.negate:
            return f"not in [{range_truncate(self.valid_chars)}]"
        else:
            return f"in [{range_truncate(self.valid_chars)}]"


class Repeat(Lens):
    """
    Applies a repetition of the givien lens (i.e. kleene-star).
    """

    def __init__(self, lens, min_count=1, max_count=None, **options):
        """
        Arguments:
          lens - the lens to repeat
          min_count - the min repetitions
          max_count - maximum repetitions (must be > 0 if set)
        """
        super().__init__(**options)
        assert min_count >= 0
        if has_value(max_count):
            assert max_count > min_count

        self.min_count, self.max_count = min_count, max_count
        self.extend_sublenses([lens])

    def _get(self, concrete_input_reader, current_container):
        """Calls a sequence of GETs on the sub-lens."""

        # Algorithm
        #
        # Loop until max count reached or lens fails to alter input state (which
        # could happen indefinitely.

        # For brevity.
        lens = self.lenses[0]

        # For tracking how many successful GETs
        no_got = 0

        while True:
            # Instantiate the rollback context, so we can later check if any state was changed.
            rollback_context = automatic_rollback(
                concrete_input_reader, current_container, check_for_state_change=True
            )
            try:
                with rollback_context:
                    self.container_get(lens, concrete_input_reader, current_container)

                # If the lens changed no state, then we must break, otherwise continue
                # for ever.
                if not rollback_context.some_state_changed:
                    d(
                        "Lens %s changed no state during this iteration, so we must break out - or spin for ever"
                        % lens
                    )
                    break

                no_got += 1

                # Don't get more than maximim
                if has_value(self.max_count) and no_got == self.max_count:
                    break
            except LensException:
                break

        if no_got < self.min_count:
            raise TooFewIterationsException(
                "Expected at least %s successful GETs but got only %s"
                % (self.min_count, no_got)
            )

    def _put(self, item, concrete_input_reader, current_container):
        """Calls a sequence of PUTs on the sub-lens."""

        # Algorithm
        #
        # - First we try to PUT with the lenses (first using input if it is available)
        # - Then, we must check that the minumum items have been consumed from input:
        # we may have PUT all new items (i.e. without input consumption) so still
        # need to call GET for a minimum number of times.
        # - In both cases we must break out if a lens changes no state.

        # For brevity.
        lens = self.lenses[0]

        no_got = 0  # For checking how many items of input were consumed
        no_put = 0  # For checking how many items were PUT.
        output = ""

        # This simplifies our algorithm.
        if concrete_input_reader:
            input_readers = [concrete_input_reader, None]
        else:
            input_readers = [None]

        #
        # Handle the PUT/CREATEs
        #

        for input_reader in input_readers:

            # Allows the while loop to request breakout from outer for loop.
            break_for_loop = False

            while True:
                # Call PUT on the lens and break this while loop if no state changed or we
                # get a LensException.  Also, break the for loop if we PUT max count.
                rollback_context = automatic_rollback(
                    input_reader, current_container, check_for_state_change=True
                )
                try:
                    with rollback_context:
                        put = self.container_put(lens, input_reader, current_container)
                except LensException:
                    # TODO: To support deletion (i.e. when no item matches this input, wrap lens as: lens | Empty()
                    # Infact we should not expect a LensException - only break out when no state changes.
                    break

                if not rollback_context.some_state_changed:
                    d(
                        f"Lens {lens} changed no state during this iteration, so we must break out - or spin for ever"
                    )
                    break

                output += put
                no_put += 1

                # If the lens succeeded when we used an input reader, we assume we consumed
                # input with the lens.
                if has_value(input_reader):
                    no_got += 1

                # We have PUT enough items now.
                if no_put == self.max_count:
                    d("We have put a maximum number of items now, so breaking out.")
                    break_for_loop = True
                    break

            if break_for_loop:
                break

        #
        # Now consume and discard any remaining input if necessary (i.e. if we put
        # fewer than we had originally).  This is basically the same implentation of
        # get, though we discard any items and continue to track no_got for the puts above.
        #

        max_count = self.max_count or 0
        if concrete_input_reader and no_got < max_count:

            d("Now consuming and discarding excess input.")

            # Iterate over the input with our lens, consuming as much of it as
            # possible.
            while True:
                # Instantiate the rollback context, so we can later check if any state was changed.
                rollback_context = automatic_rollback(
                    concrete_input_reader,
                    current_container,
                    check_for_state_change=True,
                )
                try:
                    with rollback_context:
                        # XXX: Inefficient to discard container items each time.
                        lens.get_and_discard(concrete_input_reader, current_container)

                    # If the lens changed no state, then we must break, otherwise continue
                    # forever.
                    if not rollback_context.some_state_changed:
                        d(
                            "Lens %s changed no state during this iteration, so we must break out - or spin for ever"
                            % lens
                        )
                        break

                    no_got += 1

                    # Don't get more than maximim
                    if has_value(self.max_count) and no_got == self.max_count:
                        break
                except LensException:
                    break

        if no_put < self.min_count:
            raise TooFewIterationsException(
                "Expected at least %s successful PUTs but put only %s"
                % (self.min_count, no_put)
            )

        # Sanity check.
        if concrete_input_reader:
            # This should not happen... I think.
            assert no_got >= self.min_count

        return output


class Empty(Lens):
    """
    Matches the empty string, used by Optional().  Can also set modes for special
    empty matches (e.g. at the start or end of a string).
    """

    # Useful modifiers for empty matches.
    START_OF_TEXT = "START_OF_TEXT"
    END_OF_TEXT = "END_OF_TEXT"

    def __init__(self, mode=None, **options):
        super().__init__(**options)
        self.default = ""
        self.mode = mode

    def _get(self, concrete_input_reader, current_container):

        # Check for special modes.
        if self.mode == self.START_OF_TEXT:
            if concrete_input_reader.get_pos() != 0:
                raise LensException("Will match only at start of text.")
        elif self.mode == self.END_OF_TEXT:
            if not concrete_input_reader.is_fully_consumed():
                raise LensException("Will match only at end of text.")

        # Note that, useless as it is, this is actually an item that could potentially be stored that we
        # return, which is why we must explicitly check for None elsewhere in the
        # framework (e.g. use has_value(...)), since "" == False but "" != None.
        if self.has_type():
            return ""
        return None

    def _put(self, item, concrete_input_reader, current_container):

        if self.has_type():
            if not (has_value(item) and isinstance(item, str) and item == ""):
                raise LensException("Expected to PUT an empty string")
        else:
            # Should not have been passed an item.
            if has_value(item):
                raise LensException(
                    "Did not expect a non-store lens to be passed an item"
                )

            # We could be called if there is concrete input, such that our default did not intercept.
            assert_msg(
                has_value(concrete_input_reader),
                "_put() should never be called on a non-store Empty lens without concrete input.",
            )

        # Here goes nothing!
        return ""


class Group(Lens):
    """
    A convenience lens that thinly wraps any lens, basically to set a type.
    Usually this is used to close off a lenses container.
    """

    def __init__(self, lens, **options):
        super().__init__(**options)
        assert_msg(self.has_type(), f"To be meaningful, you must set a type on {self}")
        self.extend_sublenses([lens])

    def _get(self, concrete_input_reader, current_container):
        return self.lenses[0].get(concrete_input_reader, current_container)

    def _put(self, item, concrete_input_reader, current_container):
        return self.lenses[0].put(item, concrete_input_reader, current_container)


G = Group


class Literal(Lens):
    """
    A lens that deals with a constant string, usually that will not be stored.
    """

    # TODO: Add case insensitivity.

    def __init__(self, literal_string, **options):
        assert isinstance(literal_string, str) and len(literal_string) > 0
        super().__init__(**options)
        self.literal_string = literal_string
        if not self.has_type():
            self.default = self.literal_string

    def _get(self, concrete_input_reader, current_container):
        """
        Consumes a valid char form the input, returning it if we are a STORE
        lens.
        """
        input_string = None
        try:
            input_string = concrete_input_reader.consume_string(
                len(self.literal_string)
            )
            if input_string != self.literal_string:
                raise LensException(
                    "Expected the literal '%s' but got '%s'."
                    % (
                        escape_for_display(self.literal_string),
                        escape_for_display(input_string),
                    )
                )
        except EndOfStringException:
            raise LensException(
                "Expected literal '%s' but at end of string."
                % (escape_for_display(self.literal_string))
            )

        if self.has_type():
            return input_string
        else:
            return None

    def _put(self, item, concrete_input_reader, current_container):
        """
        If a store lens, tries to output the given char; otherwise outputs
        original char from concrete input.
        """
        # If we are not a store lens, simply return what we would consume from the input.
        if not self.has_type():
            # We should not have been passed an item.
            assert_msg(
                not has_value(item),
                f"{self} did not expected to be passed an item - is a non-store lens",
            )
            if has_value(concrete_input_reader):
                concrete_start_position = concrete_input_reader.get_pos()
                self._get(concrete_input_reader, current_container)
                return concrete_input_reader.get_consumed_string(
                    concrete_start_position
                )

            else:
                raise NoDefaultException(
                    "Cannot CREATE: a default should have been set on lens %s, or a higher lens."
                    % self
                )

        # If this is PUT (vs CREATE) then first consume input.
        if concrete_input_reader:
            self.get(concrete_input_reader)

        if item != self.literal_string:
            raise LensException(f"{self} can not PUT {item}.")

        return item

    def _display_id(self):
        """To aid debugging."""
        # Name is only set after Lens constructor called.
        if hasattr(self, "name") and has_value(self.name):
            return self.name
        return f"'{escape_for_display(self.literal_string)}'"
