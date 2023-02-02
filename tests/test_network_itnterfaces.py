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
#
#
# Original Author: Nick Blundell <blundeln [AT] gmail [DOT] com>
# Organisation: www.nickblundell.org.uk
#
# Description:
#   Some tests that serve as more complex examples
#
from pylens import get, put
from pylens.base_lenses import Group
from pylens.containers import Container, LensObject
from pylens.core_lenses import Until
from pylens.debug import assert_equal, describe_test
from pylens.settings import GlobalSettings
from pylens.util_lenses import (
    NL,
    WS,
    BlankLine,
    HashComment,
    KeyValue,
    Keyword,
    List,
    ZeroOrMore,
)


# First we define a class to represent the iface stanza.  I break it up a
# little to make it clearer.
class NetworkInterface(LensObject):
    # Some component lenses.
    indent = WS("   ")
    interface_attribute = KeyValue(
        indent
        + Keyword(additional_chars="_-", is_label=True)
        + WS(" ")
        + Until(NL(), type=str)
        + NL()
    )

    # Put it all together.
    __lens__ = (
        "iface"
        + WS(" ")
        + Keyword(additional_chars="_-", is_label=True)
        + WS(" ")
        + Keyword(label="address_family")
        + WS(" ")
        + Keyword(label="method")
        + NL()
        + ZeroOrMore(interface_attribute)
    )

    def __init__(self, **kargs):
        """A simple constructor, which simply store keyword args as attributes."""
        for key, value in kargs.items():
            setattr(self, key, value)

    # Define label mappings, so labels such as "dns-nameservers" are mapped to and
    # from a valid python identifier such as "dns_nameservers" and can
    # therefore be manipulated as object attributes.
    def _map_label_to_identifier(self, label):
        return label.replace("-", "_")

    def _map_identifier_to_label(self, attribute_name):
        return attribute_name.replace("_", "-")


# Now we can define a class to represent the whole configuration, such that
# it will contain NetworkInterface objects, etc.
class InterfaceConfiguration(LensObject):
    auto_lens = Group(
        "auto"
        + WS(" ")
        + List(Keyword(additional_chars="_-", type=str), WS(" "), type=None)
        + WS("")
        + NL(),
        type=list,
        name="auto_lens",
    )
    __lens__ = ZeroOrMore(NetworkInterface | auto_lens | HashComment() | BlankLine())

    # Define containers within this container.
    interfaces = Container(store_items_of_type=[NetworkInterface], type=dict)
    auto_interfaces = Container(store_items_from_lenses=[auto_lens], type=list)


INPUT = """\
iface eth0-home inet static
   address 192.168.1.1
   netmask 255.255.255.0
   gateway  67.207.128.1
   dns-nameservers 67.207.128.4 67.207.128.5
   up flush-mail

auto lo eth0
# A comment
auto eth1 
"""


def test_get_if_config():
    """
    This is an example of how we could embedded lenses within classes to
    manipulate the widely used interfaces.conf file to configure network
    interfaces of a UNIX systems.

    Note that it does not aim to be complete, just a demonstration of how you
    could compose such a mapping.
    """
    describe_test("GET InterfaceConfiguration")
    config = get(InterfaceConfiguration, INPUT)
    assert_equal(config.interfaces["eth0-home"].address, "192.168.1.1")
    assert_equal(config.auto_interfaces[0][1], "eth0")
    assert_equal(len(config.auto_interfaces), 2)


def test_put_if_config():
    describe_test("PUT InterfaceConfiguration")
    config = get(InterfaceConfiguration, INPUT)
    config.interfaces["eth0-home"].netmask = "bananas"
    config.auto_interfaces[0].insert(1, "wlan2")
    output = put(config)
    expected = """\
iface eth0-home inet static
   address 192.168.1.1
   gateway  67.207.128.1
   dns-nameservers 67.207.128.4 67.207.128.5
   up flush-mail
   netmask bananas

auto lo wlan2 eth0
# A comment
auto eth1 
"""
    assert output == expected


def test_create_if_config():
    describe_test("CREATE InterfaceConfiguration")
    GlobalSettings.check_consumption = True
    interface = NetworkInterface(
        address_family="inet",
        method="static",
        dns_nameservers="1.2.3.4 1.2.3.5",
        netmask="255.255.255.0",
    )
    interface.some_thing = "something or another"
    config = InterfaceConfiguration()
    config.interfaces = {"eth3": interface}
    config.auto_interfaces = [["eth0"], ["wlan2", "eth2"]]

    output = put(config)
    expected = """\
iface eth3 inet static
   dns-nameservers 1.2.3.4 1.2.3.5
   netmask 255.255.255.0
   some-thing something or another
auto eth0
auto wlan2 eth2
"""
    assert expected == output
