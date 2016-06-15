# Copyright (c) 2015 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy

import mock
from oslo_utils import uuidutils

from neutron.api.rpc.callbacks.consumer import registry as consumer_reg
from neutron.api.rpc.callbacks import events
from neutron.api.rpc.callbacks import resources
from neutron.agent.common import ovs_lib
from neutron.agent.l2.extensions import trunk
from neutron.tests.common.agents import l2_extensions
from neutron.tests.functional.agent.l2 import base


class OVSAgentTrunkExtensionTestFramework(base.OVSAgentTestFramework):
    def setUp(self):
        super(OVSAgentTrunkExtensionTestFramework, self).setUp()
        self.config.set_override('extensions', ['trunk'], 'agent')

    def _get_device_details(self, port, network):
        dev = super(OVSAgentTrunkExtensionTestFramework,
                    self)._get_device_details(port, network)
        dev['is_trunk'] = True
        return dev

    def _plug_ports(self, network, ports, agent, bridge=None, namespace=None):
        # create the bridge and a port
        for port in ports:
            trunk_bridge = trunk.TrunkAgentExtension._gen_trunk_br_name(
                port['id'])
            self.addCleanup(self.ovs.delete_bridge, trunk_bridge)
            br = self.ovs.add_bridge(trunk_bridge)
            self.driver.plug(
                network.get('id'), port.get('id'), port.get('vif_name'),
                port.get('mac_address'),
                trunk_bridge)

class TestOVSAgentTrunkExtension(OVSAgentTrunkExtensionTestFramework):

    def test_trunk_creation(self):
        """Make sure bandwidth limit rules are set in low level to ports."""

        self.setup_agent_and_ports(
            port_dicts=self.create_test_ports(amount=1))
        self.wait_until_ports_state(self.ports, up=True)
