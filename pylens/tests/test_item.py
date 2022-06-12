from pylens.debug import d
from pylens.item import enable_meta_data


def test_item_meta():
    d("Started")
    item = "hello"
    item = enable_meta_data(item)

    # Should be able to add any attribute.
    item._meta_data.monkeys = True
    assert item._meta_data.monkeys == True
    assert item._meta_data.bananas == None
