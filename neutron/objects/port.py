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
from neutron.objects import base
from neutron.plugins.ml2 import models as ml2_models


@obj_base.VersionedObjectRegistry.register
class PortBinding(base.NeutronDbObject):

    db_model = ml2_models.PortBinding

    fields = {
        'port_id': obj_fields.UUIDField(),
        'host': obj_fields.StringField(),
        'vnic_type': obj_fields.StringField(),
        'profile': obj_fields.StringField(),
        'vif_details': obj_fields.StringField(),
        'vif_type': obj_fields.StringField()
    }


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

    #port_binding_model = qos_db_model.QosPortPolicyBinding
    #network_binding_model = qos_db_model.QosNetworkPolicyBinding

    fields = {
        'id': obj_fields.UUIDField(),
        'tenant_id': obj_fields.UUIDField(),
        'name': obj_fields.StringField(),
        'network_id': obj_fields.UUIDField(), #correct?
        'mac_address': obj_fields.MACAddressField,
        'admin_state_up': obj_fields.BooleanField(),
        'device_owner': obj_fields.StringField(),
        'device_id': obj_fields.StringField(),
        'dns_name': obj_fields.StringField(),
        'fixed_ips': obj_fields.ListOfObjectsField('IPAllocation', subclasses=True),
        'status': obj_fields.StringField(),
        'binding': obj_fields.ObjectField('PortBinding', subclasses=True,
                                          nullable=True)
    }

    @classmethod
    def _get_object_port(cls, context, model, **kwargs):
        with db_api.autonested_transaction(context.session):
            binding_db_obj = db_api.get_object(context, model, **kwargs)
            if binding_db_obj:
                return cls.get_by_id(context, binding_db_obj['policy_id'])

    @classmethod
    def get_port_bindings(cls, context, port_id):
        with db_api.autonested_transaction(context.session):
            binding_db_obj = db_api.get_object(context, ml2_models.PortBinding, port_id=port_id)
            if binding_db_obj:
                return cls.get_by_id(context, binding_db_obj['id'])

    @classmethod
    def associate_port_bindings(cls, context, port_id):
        obj_api.associate_port_to_portbinding(context, port_id)
    #fields_no_update = ['id', 'tenant_id']

    #synthetic_fields = ['fixed_ips']

#class PortNetworkBinding

#class PortFixedIP
#    @staticmethod
#    def _from_db_object(context, port, db_port):
#        import pdb; pdb.set_trace()  # XXX BREAKPOINT
#        for field in port.fields:
#            port[field] = db_port[field]
#            #port._context = context
#            #port.obj_reset_changes()
#            return port
#
#    @classmethod
#    def get_by_id(cls, context, id):
#        db_obj = db_api.get_object(context, cls.db_model, id=id)
#        if db_obj:
#            return cls._from_db_object(context, cls(context), db_obj)
