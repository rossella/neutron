import mock

from neutron import context
from neutron.db import api as db_api
from neutron.db import models_v2
from neutron.objects import port
from neutron.tests import base as test_base
from neutron.tests.unit import testlib_api


SQLALCHEMY_COMMIT = 'sqlalchemy.engine.Connection._commit_impl'


binding = port.PortBindingObject(id=2, vif_type="muu")

fake_port = {
    'id': 'fake_id',
    #'tenant_id': obj_fields.UUIDField(),
     'name': 'test',
     'binding': binding
}


class PortTestCase(test_base.BaseTestCase):

    _test_class = port.Port

    def setUp(self):
        super(PortTestCase, self).setUp()
        self.context = context.get_admin_context()

    @mock.patch('nova.db.network_get')
    def test_get_by_id(self, get):

        with mock.patch.object(db_api, 'get_object',
                               return_value=fake_port) as get_object_mock:
            import pdb; pdb.set_trace()  # XXX BREAKPOINT
            obj = self._test_class.get_by_id(self.context, id='fake_id')
            #self.assertTrue(self._is_test_class(obj))
            #self.assertEqual(self.db_obj, get_obj_db_fields(obj))
            get_object_mock.assert_called_once_with(
                self.context, self._test_class.db_model, id='fake_id')


class PortDbObjectTestCase(test_base.BaseDbObjectTestCase,
                                testlib_api.SqlTestCase):

    _test_class = port.Port

    def setUp(self):
        super(PortDbObjectTestCase, self).setUp()
        self._create_test_network()

    def _create_test_port(self):
        port_obj = port.Port(self.context, **self.db_obj)
        port_obj.create()
        return port_obj

    def test_attach_port_binding(self):

        obj = self._create_test_port()
        self.assertIsNone(obj.get_port_bindings(context, obj['id']))

        # Now attach policy and repeat
        obj.associate_port_bindings(context, obj['id'])

        binding_obj = port.Port.get_port_bindings(context, obj['id'])
        port = port.Port.get_by_id(context, obj['id'])
        self.assertEqual(port.binding, binding_obj)


    def _create_test_network(self):
        # TODO(ihrachys): replace with network.create() once we get an object
        # implementation for networks
        self._network = db_api.create_object(self.context, models_v2.Network,
                                             {'name': 'test-network1'})
