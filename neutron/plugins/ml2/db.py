# Copyright (c) 2013 OpenStack Foundation
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

import collections

from sqlalchemy import or_
from sqlalchemy.orm import exc

from neutron.db import api as db_api
from neutron.db import models_v2
from neutron.db import securitygroups_db as sg_db
from neutron.extensions import portbindings
from neutron import manager
from neutron.openstack.common import log
from neutron.openstack.common import uuidutils
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import models

LOG = log.getLogger(__name__)

# limit the number of port OR LIKE statements in one query
MAX_PORTS_PER_QUERY = 500


def add_network_segment(session, network_id, segment):
    with session.begin(subtransactions=True):
        record = models.NetworkSegment(
            id=uuidutils.generate_uuid(),
            network_id=network_id,
            network_type=segment.get(api.NETWORK_TYPE),
            physical_network=segment.get(api.PHYSICAL_NETWORK),
            segmentation_id=segment.get(api.SEGMENTATION_ID)
        )
        session.add(record)
    LOG.info(_("Added segment %(id)s of type %(network_type)s for network"
               " %(network_id)s"),
             {'id': record.id,
              'network_type': record.network_type,
              'network_id': record.network_id})


def get_network_segments(session, network_id):
    with session.begin(subtransactions=True):
        records = (session.query(models.NetworkSegment).
                   filter_by(network_id=network_id))
        return [{api.ID: record.id,
                 api.NETWORK_TYPE: record.network_type,
                 api.PHYSICAL_NETWORK: record.physical_network,
                 api.SEGMENTATION_ID: record.segmentation_id}
                for record in records]


def ensure_port_binding(session, port_id):
    with session.begin(subtransactions=True):
        try:
            record = (session.query(models.PortBinding).
                      filter_by(port_id=port_id).
                      one())
        except exc.NoResultFound:
            record = models.PortBinding(
                port_id=port_id,
                vif_type=portbindings.VIF_TYPE_UNBOUND)
            session.add(record)
        return record


def get_port(session, port_id):
    """Get port record for update within transcation."""

    with session.begin(subtransactions=True):
        try:
            record = (session.query(models_v2.Port).
                      filter(models_v2.Port.id.startswith(port_id)).
                      one())
            return record
        except exc.NoResultFound:
            return
        except exc.MultipleResultsFound:
            LOG.error(_("Multiple ports have port_id starting with %s"),
                      port_id)
            return


def get_port_from_device_mac(device_mac):
    LOG.debug(_("get_port_from_device_mac() called for mac %s"), device_mac)
    session = db_api.get_session()
    qry = session.query(models_v2.Port).filter_by(mac_address=device_mac)
    return qry.first()


def get_ports_and_sgs(port_ids):
    """Get ports from database with security group info."""

    # break large queries into smaller parts
    if len(port_ids) > MAX_PORTS_PER_QUERY:
        LOG.debug("Number of ports %(pcount)s exceeds the maximum per "
                  "query %(maxp)s. Partitioning queries.",
                  {'pcount': len(port_ids), 'maxp': MAX_PORTS_PER_QUERY})
        return (get_ports_and_sgs(port_ids[:MAX_PORTS_PER_QUERY]) +
                get_ports_and_sgs(port_ids[MAX_PORTS_PER_QUERY:]))

    LOG.debug("get_ports_and_sgs() called for port_ids %s", port_ids)

    if not port_ids:
        # if port_ids is empty, avoid querying to DB to ask it for nothing
        return []
    ports_to_sg_ids = get_sg_ids_grouped_by_port(port_ids)
    return [make_port_dict_with_security_groups(port, sec_groups)
            for port, sec_groups in ports_to_sg_ids.iteritems()]


def get_sg_ids_grouped_by_port(port_ids):
    sg_ids_grouped_by_port = collections.defaultdict(list)
    session = db_api.get_session()
    sg_binding_port = sg_db.SecurityGroupPortBinding.port_id

    with session.begin(subtransactions=True):
        # partial UUIDs must be individually matched with startswith.
        # full UUIDs may be matched directly in an IN statement
        partial_uuids = set(port_id for port_id in port_ids
                            if not uuidutils.is_uuid_like(port_id))
        full_uuids = set(port_ids) - partial_uuids
        or_criteria = [models_v2.Port.id.startswith(port_id)
                       for port_id in partial_uuids]
        if full_uuids:
            or_criteria.append(models_v2.Port.id.in_(full_uuids))

        query = session.query(models_v2.Port,
                              sg_db.SecurityGroupPortBinding.security_group_id)
        query = query.outerjoin(sg_db.SecurityGroupPortBinding,
                                models_v2.Port.id == sg_binding_port)
        query = query.filter(or_(*or_criteria))

        for port, sg_id in query:
            if sg_id:
                sg_ids_grouped_by_port[port].append(sg_id)
    return sg_ids_grouped_by_port


def make_port_dict_with_security_groups(port, sec_groups):
    plugin = manager.NeutronManager.get_plugin()
    port_dict = plugin._make_port_dict(port)
    port_dict['security_groups'] = sec_groups
    port_dict['security_group_rules'] = []
    port_dict['security_group_source_groups'] = []
    port_dict['fixed_ips'] = [ip['ip_address']
                              for ip in port['fixed_ips']]
    return port_dict


def get_port_binding_host(port_id):
    session = db_api.get_session()
    with session.begin(subtransactions=True):
        try:
            query = (session.query(models.PortBinding).
                     filter(models.PortBinding.port_id.startswith(port_id)).
                     one())
        except exc.NoResultFound:
            LOG.debug(_("No binding found for port %(port_id)s"),
                      {'port_id': port_id})
            return
    return query.host
