# Copyright (c) 2010, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from .exceptions import EndOfStringException
from .rollback import Rollbackable
from .util import truncate


class ConcreteInputReader(Rollbackable):
    """Stateful reader of the concrete input string."""

    def __init__(self, input_string):
        # If input_string is in fact a ConcreteInputReader, copy its state.
        if isinstance(input_string, self.__class__):
            self.position = input_string.position
            self.string = input_string.string
        # Otherwise, initialise our state.
        else:
            assert isinstance(input_string, str)
            self.position = 0
            self.string = input_string

    def reset(self):
        self.set_pos(0)

    def _get_state(self, copy_state=True):
        return self.get_pos()

    def _set_state(self, state, copy_state=True):
        self.set_pos(state)

    def get_consumed_string(self, start_pos=0):
        return self.string[start_pos : self.position]

    def get_pos(self):
        return self.position

    def set_pos(self, pos):
        assert isinstance(pos, int)
        self.position = pos

    def get_remaining(self):
        """Return the text that remains to be parsed - useful for debugging."""
        return self.string[self.position :]

    def consume_string(self, length):
        """
        Consume a string of specified length from the input.
        """
        if self.position + length > len(self.string):
            raise EndOfStringException()

        start = self.position
        self.position += length
        return self.string[start : self.position]

    def consume_char(self):
        """
        Consume and return the next char from input.
        """
        if self.is_fully_consumed():
            raise EndOfStringException()

        char = self.string[self.position]
        self.position += 1
        return char

    def is_fully_consumed(self):
        """
        Return whether the string is fully consumed
        """
        return self.position >= len(self.string)

    def is_aligned_with(self, other):
        """Check if this reader is aligned with another."""
        return self.position == other.position and self.string == other.string

    def __str__(self):
        # Return a string representation of this reader, to help debugging.
        if self.is_fully_consumed():
            return "END_OF_STRING"

        display_string = self.string[self.position :]
        return "'" + truncate(display_string) + "'"

    __repr__ = __str__
