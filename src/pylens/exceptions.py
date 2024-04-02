# Copyright (c) 2010, Nick Blundell
# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

from .debug import IN_DEBUG_MODE, d


# Thrown when tentative object state should be rolled back.
class RollbackException(Exception):
    pass


class LensException(RollbackException):
    """
    Thrown when parsing or creating lenses to trigger rollback, such that parsing
    may resume at a higher level (e.g. to try another lens path), if possible.
    """

    def __init__(self, msg=None):
        self.__msg = msg
        if IN_DEBUG_MODE:
            d(f"Throwing: {self.__msg} (from {self.get_thrown_from()})")

    def get_thrown_from(self):
        import inspect

        from nbdebug import getCallerLocation

        # TODO: Could tidy this up and perhaps integrate with nbdebug.

        ignore_frames = [
            "lens_assert()",
            "LensException.get_thrown_from()",
            "LensException.__init__()",
        ]
        callerFrame = inspect.currentframe()
        location = None
        while callerFrame:
            location = getCallerLocation(callerFrame)
            if location not in ignore_frames:
                break
            callerFrame = callerFrame.f_back

        return location

    def __str__(self):
        return f"LensException: {self.__msg}"


# Thrown when an abstract token collection cannot find an appropriate token in the
# PUT direction.
# Note, when deciding whether to throw a LensException or Exception it is useful
# to consider the Or lens, when alternate branches may be tried (e.g. is it a
# problem with the lens definition or just a failed parsing branch)
class NoTokenToConsumeException(LensException):
    pass


class NoDefaultException(LensException):
    pass


class TooFewIterationsException(LensException):
    pass


class NotFullyConsumedException(LensException):
    pass


# Thrown when it looks like a lens may iterate infinitely.
class InfiniteIterationException(LensException):
    pass  # XXX Deprecated


class InfiniteRecursionException(Exception):
    pass


class CannotStoreException(Exception):
    pass


class EndOfStringException(LensException):
    pass
