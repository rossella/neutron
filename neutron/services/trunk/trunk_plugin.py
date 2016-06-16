# Copyright 2016 SUSE Linux Products GmbH
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


from neutron.services.trunk.notification_drivers import driver
from neutron.services import service_base


class TrunkPlugin(service_base.ServicePluginBase):
    """Implementation of the Neutron Trunk Service Plugin."""
    supported_extension_aliases = ['trunk']

    def __init__(self):
        super(TrunkPlugin, self).__init__()
        self.notification_driver = (
            driver.RpcTrunkServiceNotificationDriver())

    def create_trunk(self, context, trunk):
        #TODO(rossella_s) write data into the DB
        self.notification_driver.create_trunk(self, context, trunk)
        return

    def delete_trunk(self, context, trunk):
        #TODO(rossella_s) write data into the DB
        self.notification_driver.delete_trunk(self, context, trunk)
        return

    def update_trunk(self, context, trunk):
        #TODO(rossella_s) write data into the DB
        self.notification_driver.update_trunk(self, context, trunk)
        return

    def create_subport(self, context, subport):
        #TODO(rossella_s) write data into the DB
        self.notification_driver.create_subport(self, context, subport)
        return

    def delete_subport(self, context, subport):
        #TODO(rossella_s) write data into the DB
        self.notification_driver.delete_subport(self, context, subport)
        return