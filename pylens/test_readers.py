from pylens.exceptions import LensException
from pylens.readers import ConcreteInputReader
from pylens.rollback import automatic_rollback


def test_readers():
    concrete_reader = ConcreteInputReader("ABCD")
    output = ""
    for i in range(0, 2):
        output += concrete_reader.consume_char()
    assert not concrete_reader.is_fully_consumed()
    assert concrete_reader.get_remaining() == "CD"
    assert concrete_reader.get_consumed_string(0) == "AB"

    for i in range(0, 2):
        output += concrete_reader.consume_char()
    assert output == "ABCD"
    assert concrete_reader.is_fully_consumed()

    concrete_reader = ConcreteInputReader("ABCD")

    # Now test with rollback.
    concrete_reader = ConcreteInputReader("ABCD")
    try:
        with automatic_rollback(concrete_reader):
            concrete_reader.consume_char()
            assert concrete_reader.get_remaining() == "BCD"
            raise LensException()
    except LensException:
        pass  # Don't want to stop tests.

    assert concrete_reader.get_remaining() == "ABCD"

    # Test that clones share the string object, for efficiency.
    cloned_reader = ConcreteInputReader(concrete_reader)
    assert cloned_reader.string is concrete_reader.string
    assert cloned_reader.is_aligned_with(concrete_reader)
    cloned_reader.position += 1
    assert not cloned_reader.is_aligned_with(concrete_reader)
