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
from oslo_log import log as logging

from neutron.api.rpc.callbacks import events
from neutron.api.rpc.callbacks.producer import registry
from neutron.api.rpc.callbacks import resources
from neutron.api.rpc.handlers import resources_rpc


LOG = logging.getLogger(__name__)


def _get_trunk(trunk_id, **kwargs):
    #TODO(rossella_s) implement
    return

def _get_subport(subport_id, **kwargs):
    #TODO(rossella_s) implement
    return

class RpcTrunkServiceNotificationDriver():
    """RPC message queue service notification driver for trunk."""

    def __init__(self):
        self.notification_api = resources_rpc.ResourcesPushRpcApi()
        registry.provide(_get_trunk, resources.TRUNK)
        registry.provide(_get_subport, resources.SUBPORT)

    def get_description(self):
        return "Message queue updates"

    def create_trunk(self, context, trunk):
        #No need to update agents on create
        pass

    def delete_trunk(self, context, trunk):
        #No need to update agents on create
        pass

    def update_trunk(self, context, trunk):
        self.notification_api.push(context, trunk, events.CREATED)

    def create_subport(self, context, subport):
        self.notification_api.push(context, subport, events.CREATED)

    def delete_subport(self, context, subport):
        self.notification_api.push(context, subport, events.DELETED)