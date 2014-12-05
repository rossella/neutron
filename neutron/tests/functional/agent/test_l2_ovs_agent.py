# Copyright (c) 2014 Red Hat, Inc.
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

import eventlet
import mock
import netaddr
import uuid

from neutron.agent.common import config as agent_config
from neutron.agent.linux import interface
from neutron.agent.linux import ip_lib
from neutron.agent.linux import polling
from neutron.agent.linux import ovs_lib
from neutron.agent.linux import utils as agent_utils
from neutron.openstack.common import uuidutils
from oslo_log import log as logging
from neutron.plugins.common import constants as p_const
from neutron.plugins.openvswitch.agent import ovs_neutron_agent as ovs_agent
from neutron.plugins.openvswitch.common import config as ovs_config
from neutron.tests.common import net_helpers
from neutron.tests.functional.agent.linux import base
from neutron.tests.functional.common import utils

from oslo.config import cfg

LOG = logging.getLogger(__name__)


class L2AgentOVSTestFramework(base.BaseOVSLinuxTestCase):

    br_int = "test-br-int"
    br_tun = "test-br-tun"
    patch_tun = "%s-patch-tun" % br_int
    patch_int = "%s-patch-int" % br_tun

    _TEST_ALLOC = [{"mac": "52:54:00:21:b3:c1", "ip": "192.168.10.200"},
                   {"mac": "52:54:00:21:b3:c2", "ip": "192.168.10.210"}]

    _TEST_TCP_PORT = 9999

    def setUp(self):
        super(L2AgentOVSTestFramework, self).setUp()
        plugin_str = ('neutron.plugins.openvswitch.agent.'
                      'ovs_neutron_agent.OVSPluginApi')
        mock.patch(plugin_str).start()
        mock.patch('neutron.agent.rpc.PluginReportStateAPI').start()
        self.agent = None
        self._configure_agent()
        self.ovs = ovs_lib.BaseOVS()
        self.cleanup_networks = []
        self.test_utils = utils.FunctionalTestUtils()

    def tearDown(self):
        for network in self.cleanup_networks:
            self._safe_cleanup_ports_and_namespace(network)
        super(L2AgentOVSTestFramework, self).tearDown()

    def _configure_agent(self):
        cfg.CONF.register_opts(interface.OPTS)
        cfg.CONF.register_opts(ovs_config.ovs_opts)
        agent_config.register_interface_driver_opts_helper(cfg.CONF)
        cfg.CONF.set_override('interface_driver',
                            'neutron.agent.linux.interface.OVSInterfaceDriver')
        cfg.CONF.set_override('integration_bridge', self.br_int)
        cfg.CONF.set_override('ovs_integration_bridge', self.br_int)
        cfg.CONF.set_override('tunnel_bridge', self.br_tun)
        cfg.CONF.set_override("int_peer_patch_port", self.patch_tun, "OVS")
        cfg.CONF.set_override("tun_peer_patch_port", self.patch_int, "OVS")
        cfg.CONF.set_override("firewall_driver",
                'neutron.agent.linux.iptables_firewall.IptablesFirewallDriver',
                "SECURITYGROUP")

    def new_agent(self, tunnel_types=p_const.TYPE_VXLAN):
        local_ip = '192.168.10.1'
        bridge_mappings = {}
        self.agent = ovs_agent.OVSNeutronAgent(self.br_int, self.br_tun,
                                               local_ip, bridge_mappings,
                                               polling_interval=10,
                                               tunnel_types=tunnel_types,
                                               prevent_arp_spoofing=False)
        if tunnel_types:
            self.addCleanup(self._cleanup_bridges, [self.br_int, self.br_tun])
        else:
            self.addCleanup(self._cleanup_bridges, [self.br_int])
        self.agent.plugin_rpc = mock.Mock()
        self.agent.sg_agent = mock.Mock()

    def _bound_test_ports(self, network):
        for i, port in enumerate(network.ports):
            vif_name = self.test_utils.get_interface_name(network.id, port)
            vif_port = ovs_lib.VifPort(vif_name, "%s" % (i), 'id-%s' % (i),
                                port.mac_address, self.agent.int_br)
            self.agent.port_bound(vif_port, network.id, p_const.TYPE_VLAN,
                                physical_network=None,
                                segmentation_id=("%s" % (i)),
                                fixed_ips=[],
                                device_owner=network.tenant_id,
                                ovs_restarted=False)

    def _safe_cleanup_ports_and_namespace(self, network):
        driver = interface.OVSInterfaceDriver(cfg.CONF)
        for port in network.ports:
            vif_name = self.test_utils.get_interface_name(network.id, port)
            driver.unplug(vif_name, bridge=self.br_int,
                        namespace=network.namespace, prefix=None)
        ip = ip_lib.IPWrapper(cfg.CONF.root_helper, network.namespace)
        if ip.netns.exists(network.namespace):
            ip.netns.delete(network.namespace)

    def _plugin_test_ports(self, network):
        driver = interface.OVSInterfaceDriver(cfg.CONF)
        for i, port in enumerate(network.ports):
            vif_name = driver.get_device_name(port)
            driver.plug(network.id, port.id, vif_name, port.mac_address,
                        self.agent.int_br.br_name, namespace=None)
            subnet_dict = network.subnets[0]
            mask = netaddr.IPNetwork(subnet_dict.cidr).prefixlen
            ip_cidrs = ["%s/%s" % (port.fixed_ips[0]['ip_address'], mask)]
            driver.init_l3(vif_name, ip_cidrs, namespace=None)

    def _create_test_network(self):
        ports = []
        net_id = uuidutils.generate_uuid()
        subnet_dict = self.test_utils.create_subnet_dict(net_id,
                                                    enable_dhcp=False, ip_v=4)
        for i, mapping in enumerate(self._TEST_ALLOC):
            port_dict = self.test_utils.create_port_dict(
                            net_id, subnet_dict.id, ip_v=4,
                            _MAC=mapping['mac'], _IP=mapping['ip'])
            ports.append(port_dict)
        return self.test_utils.create_network_dict(
            net_id, [subnet_dict], ports)

    # checks that the ports created by the agent are working correctly
    # establish simple tcp connection
    def _assert_port_tcp_test(self, port_dict, tcp_port):
            utils.serve_single_request(port_dict.fixed_ips[0]['ip_address'],
                tcp_port)
            self.assertTrue(self.test_utils.make_single_request(
                            port_dict.fixed_ips[0]['ip_address'], tcp_port))

    def _cleanup_bridges(self, bridges=[]):
        ovs = ovs_lib.BaseOVS()
        for bridge in bridges:
            ovs.delete_bridge(bridge)

    def assert_bridge(self, br, exists=True):
        self.assertEqual(exists, self.ovs.bridge_exists(br))

    def assert_bridges(self):
        for br in (self.br_tun, self.br_int):
            self.assert_bridge(br)

    def assert_patch_ports(self):
        ovs_res = self.ovs.run_vsctl(['show'])
        ports = [self.patch_tun, self.patch_int]
        for i, port in enumerate(ports):
            toks = ovs_res.split("Interface %s" % port)
            self.assertTrue('options: {peer=%s}' % ports[(i + 1) % 2]
                            in toks[1])

    def assert_bridge_ports(self, port_names=[]):
        for port in [self.patch_tun, self.patch_int]:
            self.assertTrue(self.ovs.port_exists(port))

    def assert_iptables(self, network, enabled=False):
        ip = ip_lib.IPWrapper(self.root_helper, network.namespace)
        res = ip.netns.execute(['iptables', '-L'])
        self.assertEqual(enabled, 'neutron-filter-top' in res)

    def assert_ovs_vlan_tags(self, network, bound=False):
        ovs_res = self.ovs.run_vsctl(['show'])
        for port in network.ports:
            vif_name = self.test_utils.get_interface_name(network.id, port)
            res = ovs_res.count("Port \"%s\"\n            tag:" % vif_name)
            self.assertEqual(bound, res)


class L2AgentOVSTestCase(L2AgentOVSTestFramework):

    def _expected_plugin_rpc_call(self, call, expected_devices):
        args = (args[0][1] for args in call.call_args_list)
        for devices in args:
            return expected_devices in devices

    def test_assert_port_creation(self):
        self.new_agent(tunnel_types=p_const.TYPE_VXLAN)
        self.polling_manager = polling.InterfacePollingMinimizer()
        port_id = str(uuid.uuid4())
        self.agent.plugin_rpc.get_devices_details_list.return_value = [
            {'device': port_id,
             'port_id': port_id,
             'network_id': uuid.uuid4(),
             'network_type': 'vlan',
             'physical_network': 'physnet',
             'segmentation_id': 1,
             'fixed_ips': [],
             'device_owner': 'compute',
             'admin_state_up': True}]
        self.agent.treat_vif_port = mock.Mock()
        eventlet.spawn(self.agent.rpc_loop, self.polling_manager)
        port = self.useFixture(net_helpers.OVSPortFixture(
            bridge=self.agent.int_br, port_attrs=(
                'external_ids', {
                    'iface-id': port_id,
                    'iface-status': 'active',
                    'attached-mac': '3c:97:0e:12:86:3f'}))).port
        agent_utils.wait_until_true(
            lambda: self._expected_plugin_rpc_call(
                self.agent.plugin_rpc.update_device_up, port_id))
        self.agent.run_daemon_loop = False

    def test_assert_port_vlan_tags(self):
        self.new_agent(tunnel_types=p_const.TYPE_VXLAN)
        network = self._create_test_network()
        self._plugin_test_ports(network)
        self.assert_ovs_vlan_tags(network, bound=False)
        self._bound_test_ports(network)
        self.assert_ovs_vlan_tags(network, bound=True)

    def test_assert_bridges_ports_vxlan(self):
        self.new_agent(tunnel_types=p_const.TYPE_VXLAN)
        self.assert_bridges()
        self.assert_bridge_ports()
        self.assert_patch_ports()

    def test_assert_bridges_ports_no_tunnel(self):
        self.new_agent(tunnel_types=None)
        self.assert_bridge(self.br_int)
        self.assert_bridge(self.br_tun, exists=False)
