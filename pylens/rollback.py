# Copyright (c) 2010-2011, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

import copy

from pylens.debug import d
from pylens.exceptions import RollbackException


class Rollbackable:
    """
    A class that can have its state rolled back, to undo modifications.
    A blanket deepcopy is not ideal, though we can explore more efficient
    solutions later (e.g. copy-before-modify).
    """

    # XXX: Do we always need to copy on get AND set? Have to careful that original state is not set.
    # XXX: Basically need to make sure that original state cannot be modified
    # XXX: Perhaps add copy-flag
    def _get_state(self, copy_state=True):
        """
        Gets the state of this object that is required for rollback.  This is a
        catch-all function for classes that specialise Rollbackable, though where
        possible more efficient functions should be implemented.

        Usually we will wish to obtain a copy, so the original state is not
        modified, though sometimes (e.g. when comparing states) we will not require
        a copy.
        """
        if copy_state:
            return copy.deepcopy(self.__dict__)
        else:
            return self.__dict__

    def _set_state(self, state, copy_state=True):
        """
        Sets the state of this object for rollback.  This is a
        catch-all function for classes that specialise Rollbackable, though where
        possible more efficient functions should be implemented.

        Usually we will wish to set a copy, so the original state is not
        modified, though sometimes we will not require
        a copy (e.g. if we know the original state will no longer be required).
        """
        if copy_state:
            self.__dict__ = copy.deepcopy(state)
        else:
            self.__dict__ = state

    def __eq__(self, other):
        """So we can easily compare if two objects have state of equal value."""
        # TODO: To use this is expensive and should be replaced by a more
        # efficient method
        # TODO:   perhaps a dirty-flag scheme???
        return self.__class__ == other.__class__ and self.__dict__ == other.__dict__


#
# Utility functions for getting and setting the state of multiple rollbackables.
#
def get_rollbackables_state(*rollbackables, copy_state=True, **kargs):
    """Handy function to get the state of multiple rollbackables, conviently ignoring those with value None.

    Assume we copy state, unless directed otherwise.
    """

    # Note: rollbackables must be in same order for get and set.
    rollbackables_state = []
    for rollbackable in rollbackables:
        if isinstance(rollbackable, Rollbackable):
            rollbackables_state.append(rollbackable._get_state(copy_state=copy_state))

    # if IN_DEBUG_MODE :
    #  d("Getting state : %s" % rollbackables_state)

    return rollbackables_state


def set_rollbackables_state(
    new_rollbackables_state, *rollbackables, copy_state=True, **kargs
):
    """Handy function to set the state of multiple rollbackables, conviently ignoring those with value None.

    Assume we copy state, unless directed otherwise.
    """

    # if IN_DEBUG_MODE :
    #  d("Setting state to: %s" % new_rollbackables_state)

    state_index = 0
    for rollbackable in rollbackables:
        if isinstance(rollbackable, Rollbackable):
            rollbackable._set_state(
                new_rollbackables_state[state_index], copy_state=copy_state
            )
            state_index += 1


class automatic_rollback:
    """
    Allows rollback of reader state using the 'with' statement, for cleaner
    syntax.

    Possible extensions:
    """

    def __init__(self, *rollbackables, **kargs):
        # Store the rollbackables. Note, for convenience, allow rollbackables to be None (i.e. store only Reader instances)
        self.some_state_changed = False
        self.check_for_state_change = (
            "check_for_state_change" in kargs
            and kargs["check_for_state_change"]
            or None
        )
        # Allows initial state to be reused.
        self.initial_state = "initial_state" in kargs and kargs["initial_state"] or None
        self.rollbackables = rollbackables

    def __enter__(self):
        # Store the start state of each reader, unless we have been passed some
        # initial state to reuse.
        if self.initial_state:
            self.start_state = self.initial_state
        else:
            self.start_state = get_rollbackables_state(*self.rollbackables)

    def __exit__(self, type, value, traceback):
        # If a RollbackException is thrown, revert all the rollbackables.
        if type and issubclass(type, RollbackException):
            set_rollbackables_state(self.start_state, *self.rollbackables)
            d(f"Rolled back rollbackables to: {str(self.rollbackables)}.")

        # XXX: Optimise this to first check for concrete reader.
        if self.check_for_state_change:
            # Not changing this state, so no need to copy it.
            current_state = get_rollbackables_state(
                *self.rollbackables, copy_state=False
            )
            # d("State: start: %s current: %s" % (self.start_state, current_state))
            self.some_state_changed = current_state != self.start_state

        # Note, by not returning True, we do not supress the exception, which gives
        # us maximum flexibility.
