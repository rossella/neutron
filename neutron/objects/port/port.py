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
from neutron.db import models_v2
from neutron.db import portbindings_db
from neutron.extensions import allowedaddresspairs as addr_pair
from neutron.objects import base
from neutron.objects.port.extensions.allowedaddresspairs import (
    AllowedAddressPair)  # noqa
from neutron.plugins.ml2 import models as ml2_models


#TODO(rossella_s) we need to find a way to handle different
#PortBinding object, the PortBindingPort, the ml2 PortBinding,
#the DVRPortBinding
@obj_base.VersionedObjectRegistry.register
class PortBindingPort(base.NeutronDbObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    db_model = portbindings_db.PortBindingPort

    fields = {
        'port_id': obj_fields.UUIDField(),
        'host': obj_fields.StringField(),
    }


@obj_base.VersionedObjectRegistry.register
class PortBinding(base.NeutronDbObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    db_model = ml2_models.PortBinding

    fields = {
        'port_id': obj_fields.UUIDField(),
        'host': obj_fields.StringField(),
        'vnic_type': obj_fields.StringField(),
        #TODO(rossella_s) should be 'profile': obj_fields.DictOfStringsField()
        # but we need to write method to serialize and deserialize
        'profile': obj_fields.StringField(),
        #TODO(rossella_s): should be
        #'vif_details': obj_fields.DictOfStringsField(),
        'vif_details': obj_fields.StringField(),
        'vif_type': obj_fields.StringField()
    }


@obj_base.VersionedObjectRegistry.register
class IPAllocation(base.NeutronDbObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    db_model = models_v2.IPAllocation

    fields = {
        'port_id': obj_fields.UUIDField(),
        'subnet_id': obj_fields.UUIDField(),
        'network_id': obj_fields.UUIDField(),
        'ip_address': obj_fields.StringField()
    }


@obj_base.VersionedObjectRegistry.register
class Port(base.NeutronDbObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    db_model = models_v2.Port

    fields = {
        'id': obj_fields.UUIDField(),
        'tenant_id': obj_fields.UUIDField(),
        'name': obj_fields.StringField(),
        'network_id': obj_fields.UUIDField(),
        'mac_address': obj_fields.MACAddressField(),
        'admin_state_up': obj_fields.BooleanField(),
        'device_owner': obj_fields.StringField(),
        'device_id': obj_fields.StringField(),
        'dns_name': obj_fields.StringField(),
        'fixed_ips': obj_fields.ListOfObjectsField('IPAllocation',
                                                   nullable=True),
        'status': obj_fields.StringField(),
        'binding': obj_fields.ObjectField('PortBinding', nullable=True),
        addr_pair.ADDRESS_PAIRS: obj_fields.ListOfObjectsField(
            'AllowedAddressPair',
            nullable=True),
    }

    fields_no_update = ['id']

    synthetic_fields = ['fixed_ips', 'binding', addr_pair.ADDRESS_PAIRS]

    def to_dict(self):
        dict_ = super(Port, self).to_dict()
        for field in self.synthetic_fields:
            if field in dict_:
                if isinstance(dict_[field], list):
                    dict_[field] = [obj.to_dict() for obj in dict_[field]]
                else:
                    dict_[field] = dict_[field].to_dict()
        return dict_

    @staticmethod
    def _from_db_object(context, port, db_port):
        for field in port.fields:
            if field not in port.synthetic_fields:
                port[field] = db_port[field]
        port.load_synthetic_fields()
        port._context = context
        port.obj_reset_changes()
        return port

    @classmethod
    def get_by_id(cls, context, id):
        admin_context = context.elevated()
        with db_api.autonested_transaction(admin_context.session):
            port_db = db_api.get_object(context, cls.db_model,
                                        **{cls.primary_key: id})
            if port_db:
                return cls._from_db_object(context, cls(), port_db)

    def create(self):
        with db_api.autonested_transaction(self._context.session):
            super(Port, self).create()
            self.load_synthetic_fields()

    def load_synthetic_fields(self):
        for field in self.synthetic_fields:
            objclass = obj_base.VersionedObjectRegistry.obj_classes()[
                self.fields[field].objname][0]
            objs = objclass.get_objects(self._context, port_id=self.id)
            if isinstance(self.fields[field], obj_fields.ObjectField):
                if objs:
                    setattr(self, field, objs[0])
                else:
                    setattr(self, field, None)
            elif isinstance(self.fields[field], obj_fields.ListOfObjectsField):
                if objs:
                    setattr(self, field, objs)
                else:
                    setattr(self, field, [])
            self.obj_reset_changes([field])

    def update_binding(self, context, **binding_args):
        binding_args['port_id'] = self.id
        binding_obj = PortBinding(context, **binding_args)
        binding_obj.create()
