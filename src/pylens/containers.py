# Copyright (c) 2010, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

import copy
import re

from pylens.debug import assert_msg
from pylens.exceptions import LensException, NoTokenToConsumeException
from pylens.item import enable_meta_data
from pylens.rollback import Rollbackable, automatic_rollback
from pylens.util import Properties, get_instance_attr, has_value

# Item alignment modes for containers.
SOURCE = "SOURCE"
MODEL = "MODEL"
LABEL = "LABEL"

# Just used to simplify sorting.
LARGE_INTEGER = 0xFFFFFFFF


def d(*args):
    print(args)


class AbstractContainer(Rollbackable):
    """
    Base class for all objects that store abstract items with GET and from which
    such may be retrieved for PUT.  Meta data from the lens may be used to aid
    storage and retrieval of items in the container (e.g. labels, keys, concrete
    residue).

    We must be careful to allow the state of the container to be correctly
    captured and re-instated to facilitate efficient rollback.  In the worst
    case, we can deep-copy the state, but we should avoid this by considering
    how a particular container modifies its state during GET and PUT.  For
    example, with a list we may add or remove an item but not make finer changes
    to an item; with a general class, however, this may not be the case.
    """

    def __new__(cls, *args, **kargs):
        self = super().__new__(cls)
        # Initialise some vars regardless of __init__ being called.
        self._container_lens = None
        self._label = None
        self._alignment_mode = None

        # Return the pre-__init__ instance.
        return self

    def set_container_lens(self, lens):
        # XXX: It's not the lens that's import, just that we wish to look at it to
        # set some defaults.
        # Called when put() is preparing the container for PUTting to associate it with its container lens.
        self._container_lens = lens
        # Default to MODEL alignment
        self._alignment_mode = self._container_lens.options.alignment or MODEL

    def set_label(self, label, overwrite=False):
        if not overwrite:
            assert_msg(
                isinstance(label, str),
                "The container label must be a string --- at least for the time being.",
            )
            if label and self._label:
                raise Exception(f"Container already has a label defined: {self._label}")
        self._label = label

    def get_label(self):
        return self._label

    #
    # Can overload these for more control (e.g. tentative PUT/CREATE if non-deterministic)
    #

    def get_and_store_item(self, lens, concrete_input_reader):
        """Called by lenses that store items from sub-lenses in the container (e.g. And)."""
        # Note, here the lens may not have a type, though may still return an item
        # that was GOT from a sub-lens
        item = lens.get(concrete_input_reader, self)
        if has_value(item):
            # Note, we check the actual item for is_label rather than the lens that
            # returned it, since the is_label lens may actually be a sublens.
            if item._meta_data.is_label:
                self.set_label(item)  # Store item as label.
            else:
                self.store_item(item, lens, concrete_input_reader)

    def consume_and_put_item(self, lens, concrete_input_reader):
        """Called by lenses that put items from the container into sub-lenses (e.g. And)."""
        assert lens.has_type()
        assert_msg(
            has_value(self._container_lens),
            "Our container has not been associated with a container type lens.",
        )

        # Handle is_label lens
        if lens.options.is_label:
            if not self._label:
                raise NoTokenToConsumeException(
                    "There was no item as this container's label to PUT."
                )
            output = lens.put(self._label, concrete_input_reader, None)
            self._label = None
            return output

        # Get candidates to PUT
        candidates = self.get_put_candidates(lens, concrete_input_reader)

        d(f"Unfiltered candidates: {candidates}")

        # Filter and sort them appropriately for our context (e.g. the lens, the
        # alignment mode and the current input postion.
        candidates = self.filter_and_sort_candidate_items(
            candidates, lens, concrete_input_reader
        )

        d(f"Filtered candidates: {candidates}")

        for candidate in candidates:
            try:
                # XXX : Overkill to copy initial state every time within automatic_rollback.
                with automatic_rollback(concrete_input_reader):
                    output = lens.put(candidate, concrete_input_reader, None)
                    self.remove_item(lens, candidate)
                    return output
            except LensException:
                pass

        # Didn't PUT any token.
        raise NoTokenToConsumeException()

    def filter_and_sort_candidate_items(
        self, candidate_items, lens, concrete_input_reader
    ):
        """
        In some cases we can whittle down the candidate list based on properties
        of the lens, the container's alignment mode, and our position in the
        concrete_input_reader.  We can then sort them, to give preference for which
        will be tried firstmost in the consume_and_put_item() function.
        """

        # Handle a static label lens, in which the candidate choice is
        # straightforward - here, for flexibility, we assume several items may share
        # a static label.
        if has_value(lens.options.label):
            d(f"Using static label: '{lens.options.label}'")
            # XXX: Feels a bit of a hack to use attr_label, so will think more
            # generally about this.
            valid_candidates = [
                item
                for item in candidate_items
                if lens.options.label
                in [item._meta_data.label, item._meta_data.attr_label]
            ]
            return valid_candidates

        # Handle MODEL alignment (i.e. PUT will be in order of items in the abstract
        # model).
        if self._alignment_mode == MODEL:
            # By definition, items are already in that order.
            if len(candidate_items) > 0:
                return [candidate_items[0]]
            else:
                return []

        # Handle SOURCE alignment.
        if self._alignment_mode == SOURCE:
            # Copy candidate_items.
            def get_key(item):
                if has_value(item._meta_data.concrete_start_position):
                    return item._meta_data.concrete_start_position
                return LARGE_INTEGER  # To ensure new items go on the end.

            # Sort the candiates by their source order - if they have meta on their
            # source position.
            sorted_candidate_items = sorted(candidate_items, key=get_key)
            return sorted_candidate_items
        # TODO: LABEL alignment mode

        raise Exception(f"Unknown alignment mode: {self._alignment_mode}")

    #
    # Must overload these.
    #

    def get_put_candidates(self, lens, concrete_input_reader):
        """Returns a list of candidate items that could be PUT into the lens."""
        raise NotImplementedError()

    def remove_item(self, lens, item):
        raise NotImplementedError()

    def store_item(self, item, lens, concrete_input_reader):
        raise NotImplementedError()

    def prepare_for_put(self):
        """Called prior to PUT to ensure, for example, any internal containers are wrapped as AbstractContainers."""
        pass

    def unwrap(self):
        """Unwrap to native python type where appropriate: e.g. for list and dict."""
        raise NotImplementedError()

    def is_fully_consumed(self):
        """
        A container-specific sanity check to see if this container has been fully
        consumed (i.e. all items have been PUT).

        Note, since the label item may not always be consumed (only if an is_label
        lens is used), this should be discounted.
        """
        raise NotImplementedError()


class ListContainer(AbstractContainer):
    """Most basic container, for storing items in a list."""

    def __new__(cls, *args, **kargs):
        self = super().__new__(cls)
        self.container_item = []
        return self

    def __init__(self, container_item):
        assert isinstance(container_item, list)
        self.container_item = container_item

        assert_msg(isinstance(self.container_item, list))

        # Ensure our items can carry meta data (for algorithmic convenience) and be careful
        # to preserve the incoming lists meta data by modifying it in place.
        # Perhaps this can be done in AbstractContainer
        for index, item in enumerate(self.container_item):
            self.container_item[index] = enable_meta_data(item)

    def get_put_candidates(self, lens, concrete_input_reader):
        return self.container_item

    def remove_item(self, lens, item):
        # d("Removing item %s" % item)
        self.container_item.remove(item)

    def store_item(self, item, lens, concrete_input_reader):
        self.container_item.append(item)

    def unwrap(self):
        return self.container_item

    def _get_state(self, copy_state=True):
        state = [
            copy_state and copy.copy(self.container_item) or self.container_item,
            self._label,
        ]
        return state

    def _set_state(self, state, copy_state=True):
        self.container_item = copy_state and copy.copy(state[0]) or state[0]
        self._label = state[1]

    def __str__(self):
        return str(self.container_item)

    __repr__ = __str__

    def is_fully_consumed(self):
        return len(self.container_item) == 0


class DictContainer(ListContainer):
    """Allows a list of items with labels to be accessed as a native python dict."""

    def __init__(self, container_item):
        """
        We actually use all the functionality of the ListContainer, which we
        can later unwrap to a dict, since items may carry labels in their
        meta data.
        """

        # Create new dict if not passed one to wrap.
        assert isinstance(container_item, dict)
        self.container_item = container_item

        # Create a list to hold the items.
        items_as_list = []

        # XXX: Perhaps this should got in prepare_for_put.
        # Now add the items to the list, updating their labels from keys.
        assert isinstance(container_item, dict)
        for key, item in container_item.items():
            item = enable_meta_data(item)
            item._meta_data.label = key
            items_as_list.append(item)

        super().__init__(items_as_list)

    # TODO: Choose default alignment mode in set_container_lens().

    def store_item(self, item, *args, **kargs):
        if not has_value(item._meta_data.label):
            raise LensException(f"{self} expected item {item} to have a label.")
        super().store_item(item, *args, **kargs)

    def unwrap(self):
        # First unwrap to a list.
        items_as_list = super().unwrap()

        # Then convert to a dictionary, using item labels as keys.
        items_as_dict = {}
        for item in items_as_list:
            items_as_dict[item._meta_data.label] = item
        return items_as_dict


#
# LensObject and related classes.
#

# Note that later we may manipulate attribute actions based on arbitrary
# properties set on these two classes, such as specific label-attribute
# mappings, etc.


class Attribute(Properties):
    """
    This class is used for declaring an attribute of a LensObject

    The static counter is used so we can infer the order of declaration of attributes.
    """

    counter = 0

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self._counter = self.__class__.counter
        self.__class__.counter += 1


class Container(Attribute):
    """Used for declaring a container attribute of a LensObject."""

    pass


class LensObject(AbstractContainer):
    """
    A container that stores labelled items as object attributes, providing
    simple conversion of labels to and from python identifiers to store as
    attributes.  For example an item with the label "Last Name" would be stored
    as an object attribute as "last_name".

    To enhance the default behaviour of a LensObject, it is possible to constrain
    valid attributes and to declare sub-containers (e.g. lists, dict, etc.) which
    can be used to store specific items.
    """

    # Used to help with re-generating labels from object attribute names.  The
    # class seems a good a place as any to store this globally-useful data.
    __cached_labels = {}

    def __new__(cls, *args, **kargs):
        """
        It is important that container objects can be created without arguments
        (a la serialisation), so here we initialise important internal variables before the
        __init__ is called.
        """
        self = super().__new__(cls, *args, **kargs)

        # If sub-containers have been specified on the class, instantiate them on the instance.
        self._create_containers_and_attributes()

        # Exclude attributes that should not be considered as container state.
        self._set_excluded_attributes()

        return self

    #
    # GET related.
    #

    def store_item(self, item, lens, concrete_input_reader):
        # First see if the item is to be stored in one of our containers.
        sub_container = self._get_item_sub_container(lens, item)
        if sub_container:
            d(f"Storing {item} in container {sub_container}")
            return sub_container.store_item(item, lens, concrete_input_reader)

        if not has_value(item._meta_data.label):
            raise LensException(f"{self} expected item {item} to have a label.")
        # TODO: If constrained attributes, check within set.
        setattr(self, self.map_label_to_identifier(item._meta_data.label), item)

    def unwrap(self):
        """We are both the container and the native object."""
        # XXX: Note, somewhere before PUT we must reciprocate this.
        # Unwrap any sub containers.
        for name, container in self._containers.items():
            setattr(self, name, container.unwrap())

        return self

    #
    # PUT related.
    #

    def set_container_lens(self, lens):
        # TODO: Shall we call on sub containers - perhaps not, since can set alignment from props
        super().set_container_lens(lens)
        # For a general class container, SOURCE alignment will be a more common default.
        # Maybe LABEL mode would be more suitable when I implement it.
        self._alignment_mode = self._container_lens.options.alignment or SOURCE

    def get_put_candidates(self, lens, concrete_input_reader):
        # First see if the item is to be put from one of our containers.
        sub_container = self._get_item_sub_container(lens)
        if sub_container:
            d(f"Using sub container {sub_container}")
            return sub_container.get_put_candidates(lens, concrete_input_reader)

        # Now try to find our own candidates.
        d(f"Looking for own canidates. {self.__dict__}")
        candidates = []

        # Append all of our data attributes that are not None.
        for attr_name in self._get_attribute_names():
            # Skip if the item has not been set.
            if attr_name not in self.__dict__:
                continue

            item = self.__dict__[attr_name]
            if has_value(item):
                candidates.append(item)

        return candidates

    def remove_item(self, lens, item):
        # First see if the item is to be put from one of our containers.
        sub_container = self._get_item_sub_container(lens, item)
        if sub_container:
            d(f"Removing {item} from {sub_container}")
            sub_container.remove_item(lens, item)
            return

        d(f"Preparing to remove {item}")
        for attr_name, value in self.__dict__.items():
            if value is item:
                del self.__dict__[attr_name]
                return

        raise Exception(f"Failed to remove item {item} from {self}.")

    def prepare_for_put(self):
        """Here we ensure any raw containers are wrapped as AbstractContainers - the opposite of unwrap()."""
        # Ensure all items that may be PUT may carry meta data.
        self._enable_attributes_meta()

        # Note, if there is no raw_container, __new__ would have ensure we still have an empty container in _containers
        for name, container in self._containers.items():
            # We do not use getattr, since it may return a class attribute by same name.
            raw_container = get_instance_attr(self, name, None)
            if not has_value(raw_container):
                continue  # Don't destroy empty container already prepared in __new__
            raw_container = enable_meta_data(raw_container)
            if raw_container:
                self._containers[name] = ContainerFactory.wrap_container(raw_container)

    def is_fully_consumed(self):
        # Check if our items are consumed.
        for attribute_name in self._get_attribute_names():
            if attribute_name in self.__dict__ and has_value(
                self.__dict__[attribute_name]
            ):
                return False

        # Then, check if at least one of our containers is not fully consumed.
        for sub_container in self._containers.values():
            if not sub_container.is_fully_consumed():
                return False

        return True

    #
    # Identifer mapping.
    #

    def map_label_to_identifier(self, label):
        """
        Tries to convert a typical label to a python identifier.  You may wish to
        overload this if you require more specialised conversion.
        """
        identifier = self._map_label_to_identifier(label)

        # Check we end up with a valid python keyword.
        if not re.match(r"[a-zA-Z][a-zA-Z0-9_]*$", identifier):
            raise Exception(
                "Cannot express label '%s' (converted to '%s') as a python identifer to set as an object attribute - you will have to specialise this functionality for your purposes."
                % (label, identifier)
            )

        # Cache this conversion on the class, since it may be useful to improve
        # CREATED labels.
        self.__class__.__cached_labels[identifier] = label

        return identifier

    def map_identifier_to_label(self, identifier):
        if identifier in self.__class__.__cached_labels:
            return self.__class__.__cached_labels[identifier]

        # We assume that an underscore represents a space.
        return self._map_identifier_to_label(identifier)

    # He he: Really we should use a lens for these mappings, but perhaps it's
    # easy enough to do it like this.
    def _map_label_to_identifier(self, label):
        """This might be overridded to specialise this functionality for a specific."""
        identifier = label.lower()
        # XXX: We could pre-compile this regex.
        identifier = re.sub(r"[ ]+", "_", identifier)
        return identifier

    def _map_identifier_to_label(self, identifier):
        """This might be overridded to specialise this functionality for a specific."""
        return identifier.replace("_", " ")

    #
    # Other internal functions.
    #

    def _create_containers_and_attributes(self):
        """Create any sub-containers, if declared."""
        self._containers = {}
        self._constrained_attributes = {}
        for key, value in self.__class__.__dict__.items():
            # Handle containers.
            if isinstance(value, Container):
                container_properties = value
                assert_msg(
                    has_value(container_properties.type),
                    f"You must declare a type for the container definition '{key}'.",
                )
                container = ContainerFactory.create_container(container_properties.type)
                assert_msg(
                    has_value(container),
                    f"Could not create an appropriate container for '{key}'.",
                )
                self._containers[key] = container

            # Handle explicit attributes, which will constainer those accepted and define CREATE order.
            elif isinstance(value, Attribute):
                self._constrained_attributes[key] = value

    def _get_item_sub_container(self, lens, item=None):
        # Note, for lens matching in the get direction we use item meta (since may
        # be returned from higer lens with no type, such as Or)
        # In the put direction, we can use lens, since will only put a token into a
        # type lens.
        # if has_value(item) :
        #  d(item)
        #  assert(item._meta_data.lens)

        for name, container in self._containers.items():
            container_properties = self.__class__.__dict__[name]
            d(f"looking for item to match lens {lens}")
            if (
                has_value(container_properties.store_items_from_lenses)
                and lens in container_properties.store_items_from_lenses
            ):
                return container
            elif (
                has_value(item)
                and has_value(container_properties.store_items_from_lenses)
                and has_value(item._meta_data.lens)
                and item._meta_data.lens in container_properties.store_items_from_lenses
            ):
                return container
            elif (
                has_value(container_properties.store_items_of_type)
                and type(item) in container_properties.store_items_of_type
            ):
                return container
            elif (
                lens.has_type()
                and lens.type in container_properties.store_items_of_type
            ):
                return container

        return None

    def _set_excluded_attributes(self):
        """
        In the case where the user does not constrain which attributes are treated
        as container state (i.e. to be GOT and PUT by the lens), here we try to
        exclude any attributes that are obviously not such state.  This
        automatically builds a list of attributes to exclude from our container's
        state.  This should be called on object initialisation, before any model
        attributes are asigned.

        Note that any attribute that starts with an underscore will be excluded, so
        this aims to exclude any other attributes, such as sub-container attributes.
        """
        self._excluded_attributes = list(self.__dict__.keys()) + list(
            self._containers.keys()
        )

    def _get_attribute_names(self):
        """Returns the names of attributes that are being used to hold data items."""

        # If the useable attributes have been declared, use their names here, in declaration order.
        if self._constrained_attributes:
            # Sort the items according to their declaration order - captured by a static counter in Attribute
            items = sorted(
                self._constrained_attributes.items(), key=lambda x: x[1]._counter
            )
            attributes = [item[0] for item in items]
            return attributes

        # Otherwise, use every object attribute that is not excluded.
        attributes = []
        for attr_name in self.__dict__.keys():
            if attr_name not in self._excluded_attributes and not attr_name.startswith(
                "_"
            ):
                attributes.append(attr_name)

        return attributes

    def _enable_attributes_meta(self):
        """Enables meta on attributes that may be used as container state."""
        for attr_name in self._get_attribute_names():
            if attr_name not in self.__dict__:
                continue

            item = enable_meta_data(self.__dict__[attr_name])
            self.__dict__[attr_name] = item
            # Ensure the label of the item is updated to match the current attribute
            # name.  If our label has changed, we need to regenerate a label.
            current_label = item._meta_data.label
            if not (
                has_value(current_label)
                and self.map_label_to_identifier(current_label) == attr_name
            ):
                item._meta_data.label = self.map_identifier_to_label(attr_name)
                # XXX: Feels like a hack for now, to get around issue of static labels
                # being changed incorrectly in the same way as a dynamic label
                item._meta_data.attr_label = attr_name

    def _get_state(self, copy_state=True):
        # Get our state.
        state = [copy_state and copy.copy(self.__dict__) or self.__dict__]

        # Then append state of our containers.
        for sub_container in self._containers.values():
            state.append(sub_container._get_state(copy_state=copy_state))

        return state

    def _set_state(self, state, copy_state=True):
        # XXX: Is there any conflict here with broad use of __dict__?
        # Set our state.
        self.__dict__ = copy_state and copy.copy(state[0]) or state[0]

        # Then set the state of our containers.
        i = 1
        for sub_container in self._containers.values():
            sub_container._set_state(state[i], copy_state=copy_state)
            i += 1


class ContainerFactory:
    """
    Used to create appropriate containers for particular types of lens.  For
    example, lens.type == dict -> container_class == DictContainer.
    """

    @staticmethod
    def get_container_class(incoming_type):
        """
        Returns the container class associated with this type, if there is one.
        """
        if incoming_type is None:
            return None

        # If type is already an AbstractContainer, return it.
        if issubclass(incoming_type, AbstractContainer):
            return incoming_type

        # Handle associations with native python containers.
        if issubclass(incoming_type, list):
            return ListContainer
        elif issubclass(incoming_type, dict):
            return DictContainer

        return None

    @staticmethod
    def create_container(container_type):
        """
        Tries to create a container appropriate for this lens and returns None
        if there is no associated container class.
        """
        # See if the lens type has a container class.
        container_class = ContainerFactory.get_container_class(container_type)

        if container_class is None:
            return None

        # We do not call the constructor, which may require args.
        return container_class.__new__(container_class)

    @staticmethod
    def wrap_container(incoming_object):
        """Wraps a container if possible."""
        if not has_value(incoming_object):
            return None

        if issubclass(type(incoming_object), AbstractContainer):
            container = incoming_object
        else:
            # d("Wrapping %s" % incoming_object)
            container_class = ContainerFactory.get_container_class(
                type(incoming_object)
            )
            if not has_value(container_class):
                return None

            # Pass the raw data item to wrap.
            container = container_class(incoming_object)

        # Allow the container to prepare to be PUT (e.g. wrap any sub containers).
        container.prepare_for_put()
        # Set the (consumable) label of the container based on the item's current
        # label
        container.set_label(incoming_object._meta_data.label, overwrite=True)
        return container
