# Copyright (c) 2015 Mellanox Technologies, Ltd
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

from oslo_concurrency import lockutils
from oslo_log import log as logging
from neutron_lib import constants

from neutron._i18n import _LW, _LI
from neutron.agent.l2 import agent_extension
from neutron.agent.common import ovs_lib
from neutron.api.rpc.callbacks import events
from neutron.api.rpc.callbacks import resources
from neutron.api.rpc.handlers import resources_rpc

LOG = logging.getLogger(__name__)


#TODO(rossella_s): move these to constants
TRUNK_DEV = 'tp'
SUBPORT_DEV = 'sp'

class TrunkAgentExtension(agent_extension.AgentCoreResourceExtension):
    SUPPORTED_RESOURCES = [resources.TRUNK, resources.SUBPORT]

    def initialize(self, connection, driver_type):
        """Perform Agent Extension initialization.

        """
        self.resource_rpc = resources_rpc.ResourcesPullRpcApi()
        self.br_int = self.agent_api.request_int_br().bridge
        # TODO(rossella_s) we need to create different drivers, one for
        # OVS and one for LinuxBridge
        #self.qos_driver.consume_api(self.agent_api)
        #self.qos_driver.initialize()

        #self._register_rpc_consumers(connection)

    def consume_api(self, agent_api):
        self.agent_api = agent_api

    def _register_rpc_consumers(self, connection):
        endpoints = [resources_rpc.ResourcesPushRpcCallback()]
        for resource_type in self.SUPPORTED_RESOURCES:
            # we assume that neutron-server always broadcasts the latest
            # version known to the agent
            topic = resources_rpc.resource_type_versioned_topic(resource_type)
            connection.create_consumer(topic, endpoints, fanout=True)

    def _handle_notification(self, port, event_type):
        # TODO(rossella_s) handle all the events
        if event_type == events.UPDATED:
            self.update_trunk_port(port)

    #TODO(rossella_s) we need another hook to process the trunk deletion when
    # the VM is deleted...maybe handle_port_deletion called in
    # treat_devices_removed
    def handle_port(self, context, port):
        """Handle trunk ports

        This method is called for every new port that the agent detects.
        If the port is associated with a trunk, the agent won't do any further
        processing, since the parent port is on the trunk bridge, not on
        the br-int.
        But this method will be called and the patch ports that connect
        the trunk bridge to br-int will be created. The patch on br-int will
        have in the external-ids the interface ID of the parent port. Since
        the patch is on br-int, the OVS agent will detect and process it as a
        normal port (setting the flows to tag/untag the traffic using the local
        VLAN ID of the network). When the patch port is wired, the OVS agent
        will send a notification that the device is up, since it's using the
        same interface ID as the parent port, Nova will receive it and assume
        that the parent port is UP.
        """
        # TODO(rossella_s) do we assume that get_device_details will have this
        # new entry to signal that the port is associated to a trunk?
        if not port.get('is_trunk'):
            return
        trunk_br_name = self._gen_trunk_br_name(port['port_id'])
        trunk_br = ovs_lib.OVSBridge(trunk_br_name)
        tp_patch_int, tp_patch_trunk = self._gen_trunk_patch_names(
                    port['port_id'])
        # add patch port to br-int
        # NOTE(rossella_s): the ovs agent won't process the port if it has
        # no MAC
        patch_int_attrs = [('type', 'patch'),
                           ('options', {'peer': tp_patch_trunk}),
                           ('external_ids',
                             {'attached-mac': port['mac_address'],
                              'iface-id': port['port_id']})]
        self.br_int.add_port(tp_patch_int, *patch_int_attrs)

        # these port has no external_ids, it will be ignored by the OVS agent
        patch_trunk_attrs = [('type', 'patch'),
                             ('options', {'peer': tp_patch_int})]
        # add patch port to trunk bridge
        trunk_br.add_port(tp_patch_trunk, *patch_trunk_attrs)
        #TODO(rossella_s) handle subports

        LOG.info(_LI("Added trunk for port: %s" % port['port_id']))

    @staticmethod
    def _gen_trunk_br_name(trunk_port_id):
        return ('tbr-' + trunk_port_id)[:constants.DEVICE_NAME_MAX_LEN-1]

    @staticmethod
    def _gen_trunk_patch_names(port_id):
        return (
            (TRUNK_DEV + '-int-' + port_id)[:constants.DEVICE_NAME_MAX_LEN-1],
            (TRUNK_DEV + '-trunk' + port_id)[:constants.DEVICE_NAME_MAX_LEN-1])

    @staticmethod
    def _gen_subport_patch_names(port_id):
        return (
            (SUBPORT_DEV + '-int-' + port_id)[:constants.DEVICE_NAME_MAX_LEN-1],
            (SUBPORT_DEV +'-trunk' + port_id)[:constants.DEVICE_NAME_MAX_LEN-1])

    def update_trunk_port(self, context, port):
        #TODO(rossella_s) implement
        return