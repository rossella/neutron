import mock

from neutron import context
from neutron.db import api as db_api
from neutron.db import models_v2
from neutron.objects import port
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
            import pdb; pdb.set_trace()  # XXX BREAKPOINT
            obj = self._test_class.get_by_id(self.context, id='fake_id')
            get_object_mock.assert_called_once_with(
                self.context, self._test_class.db_model, id='fake_id')


class PortDbObjectTestCase(obj_test_base.BaseDbObjectTestCase,
                           testlib_api.SqlTestCase):

    _test_class = port.Port

    def setUp(self):
        super(PortDbObjectTestCase, self).setUp()
        self.db_obj = self.get_random_fields()
        self._create_test_network()

    def _create_test_port(self):
        port_obj = port.Port(self.context, **self.db_obj)
        port_obj.network_id = self._network['id']
        port_obj.create()
        return port_obj

    def _create_test_network(self):
        # TODO(ihrachys): replace with network.create() once we get an object
        # implementation for networks
        self._network = db_api.create_object(self.context, models_v2.Network,
                                             {'name': 'test-network1'})
    def _create_test_port_binding(self, port_id):
        binding_fields = self.get_random_fields(obj_cls=port.PortBinding)
        binding_fields['port_id'] = port_id
        binding_obj = port.PortBinding(self.context, **binding_fields)
        binding_obj.create()
        return binding_obj

    def test_attach_port_binding(self):
        port_obj = self._create_test_port()
        self.assertIsNone(port_obj.get_port_binding(self.context,
                                                    port_obj['id']))

        # Now associate port binding and repeat
        binding_fields = self.get_random_fields(obj_cls=port.PortBinding)
        port_obj.update_binding(port_obj['id'], binding_fields)

        binding_obj = port.Port.get_port_binding(self.context, port_obj['id'])
        port_obj = port.Port.get_by_id(self.context, port_obj['id'])
        #TODO(rossella_s) to make this work implement obj_to_primitive
        #self.assertEqual(port_obj['binding'], binding_obj)


