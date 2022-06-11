from .debug import assert_raises, d


def test_assert_raises():
    d("Testing")

    # Assert the ZeroDivisionError is thrown.
    with assert_raises(ZeroDivisionError):
        x = 1 / 0

    # Assert that we expected the ZeroDivisionError to be thrown.
    with assert_raises(Exception):
        with assert_raises(ZeroDivisionError):
            x = 1 / 1

    # Confirm that the unexpected exception is let through.  My most beautiful test, ever!
    with assert_raises(IndexError):
        with assert_raises(ZeroDivisionError):
            x = []
            x[0] = 2
