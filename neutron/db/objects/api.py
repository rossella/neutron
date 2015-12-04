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

from oslo_db import exception as oslo_db_exception

from neutron.common import exceptions as n_exc
from neutron.plugins.ml2 import models as ml2_models


def associate_port_to_portbinding(context, port_id):
    try:
        with context.session.begin(subtransactions=True):
            db_obj = ml2_models.PortBinding(port=port_id)
            context.session.add(db_obj)
    except oslo_db_exception.DBReferenceError:
        raise n_exc.PortNotFound(port_id=port_id)