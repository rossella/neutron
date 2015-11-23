#!/usr/bin/env python

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
import argparse
import sys

from launchpadlib.launchpad import Launchpad


def is_milestone_valid(project, name):
    milestone_names = []
    for s in project.active_milestones:
        milestone_names.append(s.name)
        if name == s.name:
            return True
    print("No active milestone found")
    print("List of active milestones %s" % milestone_names)
    return False

def _search_task(project, input_query):
    print("Searching for %s", input_query)
    bugs = project.searchTasks(input_query)
    if not bugs:
        return
    gerrit_query = "("
    for b in bugs:
        gerrit_query += ("topic:bug/%d OR " % b.bug.id)
    gerrit_query = gerrit_query[:-4]
    gerrit_query += ")\n\n"
    return gerrit_query


def get_approved_rfe_query(project):
    return _search_task("tags=[\"rfe-approved\"]")


def get_critical_bugs_query(project):
    return _search_task(
        "status=[\"In Progress\"], importance=[\"Critical\"]")


def get_high_bugs_query(project):
    return _search_task(
        "status=[\"In Progress\"], importance=[\"High\"]")


def get_specs_query(project, milestone):
    print("Searching for specs...")
    query = "("
    for s in project.valid_specifications:
        if s.milestone is not None:
            if s.milestone.name == milestone:
                query += ("topic:bp/%s OR " % s.name)
    if query == "(":
        # no blueprint was found
        return
    query = query[:-4]
    query += ")\n"
    return query


def write_section(f, section_name, query):
    print(section_name)
    if query:
        f.write("[section \"")
        f.write(section_name)
        f.write("\"]\n")
        f.write("query = ")
        f.write(query)
        print(query)
    else:
        print("No result found\n")


parser = argparse.ArgumentParser(
    description='Create dashboard for critical/high bugs, approved rfe and'
                ' blueprints. A .dash file will be created in the current'
                ' folder that you can serve as input for gerrit-dash-creator.'
                ' The output of the script can be used to query Gerrit'
                ' directly.')
parser.add_argument('milestone', type=str, help='The release milestone')
parser.add_argument('--output', type=str, help='Output file')

args = parser.parse_args()
milestone = args.milestone
if args.output:
    file_name = args.output
else:
    file_name = milestone + '.dash'

cachedir = "~/.launchpadlib/cache/"
launchpad = Launchpad.login_anonymously('just testing', 'production', cachedir,
                                        version="devel")
neutron = launchpad.projects['neutron']
if not is_milestone_valid(milestone):
    sys.exit()

with open(file_name, 'w') as f:
    title = "[dashboard]\ntitle = Neutron %s Review Inbox\n" % milestone
    f.write(title)
    f.write("description = Review Inbox\n")
    f.write("foreach = (project:openstack/neutron OR "
            "project:openstack/python-neutronclient OR "
            "project:openstack/neutron-specs) status:open NOT owner:self "
            "NOT label:Workflow<=-1 "
            "NOT label:Code-Review>=-2,self branch:master\n")
    f.write("\n")

    query = get_approved_rfe_query(neutron)
    write_section(f, "Approved RFE", query)

    query = get_critical_bugs_query(neutron)
    write_section(f, "Critical Bugs", query)

    query = get_high_bugs_query(neutron)
    write_section(f, "High Bugs", query)

    query = get_specs_query(neutron, milestone)
    write_section(f, "Blueprints", query)
