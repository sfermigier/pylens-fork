# Copyright (c) 2023-2024, Abilian SAS
#
# SPDX-License-Identifier: BSD-3-Clause

# from pylens.debug import raises, d


# def test_assert_raises():
#     d("Testing")
#
#     # Assert the ZeroDivisionError is thrown.
#     with raises(ZeroDivisionError):
#         x = 1 / 0
#
#     # Assert that we expected the ZeroDivisionError to be thrown.
#     with raises(Exception):
#         with raises(ZeroDivisionError):
#             x = 1 / 1
#
#     # Confirm that the unexpected exception is let through.  My most beautiful test, ever!
#     with raises(IndexError):
#         with raises(ZeroDivisionError):
#             x = []
#             x[0] = 2
