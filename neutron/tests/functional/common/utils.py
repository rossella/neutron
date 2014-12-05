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
import httplib
import mock
import multiprocessing
import SimpleHTTPServer
import SocketServer
import time

from oslo.config import cfg

from neutron.agent.linux import dhcp
from neutron.common import constants
from neutron.openstack.common import uuidutils


def _server_process(addr, port_number):
    Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
    httpd = SocketServer.TCPServer((addr, port_number), Handler)
    #process a single request and die
    httpd.handle_request()


def serve_single_request(addr, port_number):
    p = multiprocessing.Process(target=_server_process, args=(addr,
                                port_number))
    p.start()
    #give it a chance luv
    time.sleep(1)


class FunctionalTestUtils(object):

    _MAC_ADDRESS = '24:77:03:7d:00:4c'
    _IP_ADDRS = {
        4: {
            'addr': '192.168.10.11',
            'cidr': '192.168.10.0/24',
            'gateway': '192.168.10.1'},
        6: {
            'addr': '0:0:0:0:0:ffff:c0a8:a0b',
            'cidr': '0:0:0:0:0:ffff:c0a8:a00/120',
            'gateway': '0:0:0:0:0:ffff:c0a8:a01'}, }

    def make_single_request(self, addr, port=9999):
        conn = httplib.HTTPConnection(addr, port)
        try:
            conn.request("GET", "/")
        except Exception:
            return False
        return True

    def get_interface_name(self, network, port):
        device_manager = dhcp.DeviceManager(conf=cfg.CONF,
                        root_helper=cfg.CONF.root_helper, plugin=mock.Mock())
        return device_manager.get_interface_name(network, port)

    def create_network_dict(self, net_id, subnets=None, ports=None):
        subnets = [] if not subnets else subnets
        ports = [] if not ports else ports
        net_dict = dhcp.NetModel(use_namespaces=True, d={
            "id": net_id,
            "subnets": subnets,
            "ports": ports,
            "admin_state_up": True,
            "tenant_id": uuidutils.generate_uuid(), })
        return net_dict

    def create_subnet_dict(self, net_id, enable_dhcp=True, ip_v=4):
        sn_dict = dhcp.DictModel({
            "id": uuidutils.generate_uuid(),
            "network_id": net_id,
            "ip_version": ip_v,
            "cidr": self._IP_ADDRS[ip_v]['cidr'],
            "gateway_ip": self._IP_ADDRS[ip_v]['gateway'],
            "enable_dhcp": enable_dhcp,
            "dns_nameservers": [],
            "host_routes": [], })
        if ip_v == 6:
            sn_dict['ipv6_address_mode'] = constants.DHCPV6_STATEFUL
        return sn_dict

    def create_port_dict(self, network_id, subnet_id, ip_v=4,
                        _MAC=None, _IP=None):
        _MAC = self._MAC_ADDRESS if not _MAC else _MAC
        _IP = self._IP_ADDRS[ip_v]['addr'] if not _IP else _IP
        port_dict = dhcp.DictModel({
            "id": uuidutils.generate_uuid(),
            "name": "foo",
            "mac_address": _MAC,
            "network_id": network_id,
            "admin_state_up": True,
            "device_id": uuidutils.generate_uuid(),
            "device_owner": "foo",
            "fixed_ips": [{"subnet_id": subnet_id,
                           "ip_address": _IP}], })
        return port_dict
