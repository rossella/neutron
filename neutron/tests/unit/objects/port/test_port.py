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

import mock

from neutron import context
from neutron.db import api as db_api
from neutron.objects.port.extensions import allowedaddresspairs
from neutron.objects.port import port
from neutron.tests import base as test_base
from neutron.tests.unit.objects import test_base as obj_test_base
from neutron.tests.unit import testlib_api


SQLALCHEMY_COMMIT = 'sqlalchemy.engine.Connection._commit_impl'

binding = port.PortBinding(id=2, vif_type="muu")

fake_port = {
    'id': 'fake_id',
    'tenant_id': 'test_tenant',
    'name': 'test',
    'binding': binding
}


class PortTestCase(test_base.BaseTestCase):

    _test_class = port.Port

    def setUp(self):
        super(PortTestCase, self).setUp()
        self.context = context.get_admin_context()

    def test_get_by_id(self):

        with mock.patch.object(db_api, 'get_object',
                               return_value=fake_port) as get_object_mock:
            self._test_class.get_by_id(self.context, id='fake_id')
            #NOTE(rossella_s) had to use mock.ANY because the context object is
            # different, check if it's OK or a problem
            get_object_mock.assert_has_calls([
                mock.call(
                    mock.ANY, self._test_class.db_model, id='fake_id')])


class PortDbObjectTestCase(obj_test_base.BaseDbObjectTestCase,
                           testlib_api.SqlTestCase):

    _test_class = port.Port

    def setUp(self):
        super(PortDbObjectTestCase, self).setUp()
        self._create_test_network()
        self.db_obj['network_id'] = self._network['id']
        for obj in self.db_objs:
            obj['network_id'] = self._network['id']

    def _create_test_port(self):
        port_obj = port.Port(self.context, **self.db_obj)
        port_obj.network_id = self._network['id']
        port_obj.create()
        return port_obj

    def test_attach_port_binding(self):
        port_obj = self._create_test_port()
        self.assertIsNone(port_obj.binding)

        # Now associate port binding and repeat
        binding_fields = self.get_random_fields(obj_cls=port.PortBinding)
        port_obj.update_binding(self.context, **binding_fields)

        binding_obj = port.PortBinding.get_objects(self.context,
                                                   port_id=port_obj['id'])[0]
        import pdb; pdb.set_trace()  # XXX BREAKPOINT
        port_obj = port.Port.get_by_id(self.context, port_obj['id'])
        self.assertEqual(port_obj['binding'], binding_obj)
        port_dict = port_obj.to_dict()
        self.assertEqual(port_dict['binding'], binding_obj.to_dict())

    def test_create_ip_allocations(self):
        port_obj = self._create_test_port()

        for i in range(2):
            obj_fields = self.get_random_fields(
                obj_cls=port.IPAllocation)
            obj_fields['port_id'] = port_obj['id']
            obj_fields['network_id'] = port_obj['id']
            obj = port.IPAllocation(self.context, **obj_fields)
            obj.create()

        import pdb; pdb.set_trace()  # XXX BREAKPOINT
        port_obj = port.Port.get_by_id(self.context, port_obj['id'])

    def test_create_allowed_address_pairs(self):
        port_obj = self._create_test_port()

        for i in range(2):
            obj_fields = self.get_random_fields(
                obj_cls=allowedaddresspairs.AllowedAddressPairObj)
            obj_fields['port_id'] = port_obj['id']
            obj = allowedaddresspairs.AllowedAddressPairObj(self.context,
                                                            **obj_fields)
            obj.create()

        import pdb; pdb.set_trace()  # XXX BREAKPOINT
        addr_pair_objs = allowedaddresspairs.AllowedAddressPairObj.get_objects(
            self.context, port_id=port_obj['id'])
        port_obj = port.Port.get_by_id(self.context, port_obj['id'])
        self.assertEqual(port_obj['allowed_address_pairs'], addr_pair_objs)
        port_dict = port_obj.to_dict()
        self.assertEqual(port_dict['allowed_address_pairs'],
            addr_pair_objs.to_dict())
