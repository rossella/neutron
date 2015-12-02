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

from oslo_versionedobjects import base as obj_base
from oslo_versionedobjects import fields as obj_fields

from neutron.db import api as db_api
from neutron.db.objects import api as obj_api
from neutron.db import models_v2
from neutron.db import portbindings_db
from neutron.objects import base
from neutron.plugins.ml2 import models as ml2_models

#TODO(rossella_s) we need to find a way to handle different
#PortBinding object, the PortBindingPort, the ml2 PortBinding,
#the DVRPortBinding
@obj_base.VersionedObjectRegistry.register
class PortBindingPort(base.NeutronDbObject):

    db_model = portbindings_db.PortBindingPort

    fields = {
        'port_id': obj_fields.UUIDField(),
        'host': obj_fields.StringField(),
    }

@obj_base.VersionedObjectRegistry.register
class PortBinding(base.NeutronDbObject):

    db_model = ml2_models.PortBinding

    fields = {
        'port_id': obj_fields.UUIDField(),
        'host': obj_fields.StringField(),
        'vnic_type': obj_fields.StringField(),
        'profile': obj_fields.DictOfStringsField(),
        'vif_details': obj_fields.DictOfStringsField(),
        'vif_type': obj_fields.StringField()
    }

    @classmethod
    def get_by_id(cls, context, port_id):
        db_obj = db_api.get_object(context, cls.db_model, port_id=port_id)
        if db_obj:
            obj = cls(context, **db_obj)
            obj.obj_reset_changes()
            return obj


@obj_base.VersionedObjectRegistry.register
class IPAllocation(base.NeutronDbObject):

    db_model = models_v2.IPAllocation

    fields = {
        'port_id': obj_fields.UUIDField(),
        'subnet_id': obj_fields.UUIDField(),
        'network_id': obj_fields.UUIDField(),
        'ip_address': obj_fields.IPAddressField()
    }


@obj_base.VersionedObjectRegistry.register
class Port(base.NeutronDbObject):

    db_model = models_v2.Port

    fields = {
        'id': obj_fields.UUIDField(),
        'tenant_id': obj_fields.UUIDField(),
        'name': obj_fields.StringField(),
        'network_id': obj_fields.UUIDField(), #correct?
        'mac_address': obj_fields.MACAddressField(),
        'admin_state_up': obj_fields.BooleanField(),
        'device_owner': obj_fields.StringField(),
        'device_id': obj_fields.StringField(),
        'dns_name': obj_fields.StringField(),
        'fixed_ips': obj_fields.ListOfObjectsField('IPAllocation'),
        'status': obj_fields.StringField(),
        #TODO(rossella_s) to_dict should decompact the keys of binding and
        #put them in the port object
        'binding': obj_fields.ObjectField('PortBinding', nullable=True)
    }

    synthetic_fields = ['fixed_ips', 'binding']


    @classmethod
    def get_port_binding(cls, context, port_id):
        with db_api.autonested_transaction(context.session):
            #TODO(rossella_s): create a better method to get this
            binding_db_obj = db_api.get_objects(context, ml2_models.PortBinding,
                                                port_id=port_id)
            if binding_db_obj:
                return binding_db_obj[0]

    def obj_load_attr(self, attrname):
        if attrname != 'binding':
            #TODO (rossella_s) raise better exc and implement other attr
            raise Exception("Error loading attrs")
        #TODO(rossella_s) I get an infinite cycle with hasattr
        #if not hasattr(self, attrname):
        self.load_port_binding()

    def load_port_binding(self):
        #TODO(rossella_s): create a better method to get this
        self.binding = PortBinding.get_by_id(self._context, port_id=self.port_id)

    def update_binding(self, port_id, **binding_fields):
        binding_fields['port_id'] = port_id
        binding_obj = PortBinding(self.context, **binding_fields)
        binding_obj.create()
