"""
tetration_dns_resolver.py searches tetration inventory for hosts that don't have
a known hostname (provided by the software sensor) OR that don't have a value defined
for the annotation field named passed in as an argument (--annotation)

Key arguments (required if not defined as a global variable):
--url(url path): URL of the instance
--credential(filename): path to a tetration json credential file (.json)
--annotation(string): user annotation field for tracking hostname
--scope(string): target scope for dns resolution (inventory searched will be done against this scope)
--limit(number): max results returned per inventory search (pagination limit)

Global Variables (Required if not passed as an argument above):
TETRATION_API_URL = same as --url
TETRATION_API_CRED_PATH = same as --credential
TETRATION_HOST_NAME_USER_ANNOTATION = same as --annotation
TETRATION_SCOPE_NAME = same as --scope
TETRATION_SEARCH_LIMIT = same as --limit
DNS_SERVERS = [] # Example ['8.8.8.8','8.8.1.1']

Copyright (c) 2018 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.0 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

__author__ = "Brandon Beck"
__copyright__ = "Copyright (c) 2018 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.0"


# ====================================================================================
# IMPORTS
# ------------------------------------------------------------------------------------

from tetpyclient import RestClient
import tetpyclient
import json
import requests.packages.urllib3
import sys
import os
import argparse
import time
import dns.resolver, dns.reversename
import csv

# =================================================================================

# Disable SSL cert warnings
requests.packages.urllib3.disable_warnings()

# ====================================================================================
# GLOBALS
# ------------------------------------------------------------------------------------

TETRATION_API_URL = "https://<tetration IP or Hostname>"
TETRATION_API_CRED_PATH = '<tetration credential file>.json'
TETRATION_HOST_NAME_USER_ANNOTATION = 'FQDN'
TETRATION_SCOPE_NAME = 'Default'
TETRATION_SEARCH_LIMIT = 20
DNS_SERVERS = [] # Example ['8.8.8.8','8.8.1.1']

parser = argparse.ArgumentParser(description='Tetration API Demo Script')
parser.add_argument('--url', help='Tetration URL', required=False)
parser.add_argument('--credential', help='Path to Tetration json credential file', required=False)
parser.add_argument('--annotation', help='User Annotation Field for tracking hostname', required=False)
parser.add_argument('--scope', help='Target scope for DNS resolution', required=False)
parser.add_argument('--limit', help='Results limit for inventory search', required=False)
args = parser.parse_args()

TETRATION_API_URL = args.url if args.url else TETRATION_API_URL
TETRATION_API_CRED_PATH = args.credential if args.credential else TETRATION_API_CRED_PATH
TETRATION_HOST_NAME_USER_ANNOTATION = args.annotation if args.annotation else TETRATION_HOST_NAME_USER_ANNOTATION
TETRATION_SCOPE_NAME = args.scope if args.scope else TETRATION_SCOPE_NAME
TETRATION_SEARCH_LIMIT = args.limit if args.limit else TETRATION_SEARCH_LIMIT

resolver = dns.resolver.Resolver()

if len(DNS_SERVERS) > 0:
    resolver.nameservers = DNS_SERVERS

'''
====================================================================================
Class Constructor
------------------------------------------------------------------------------------
'''
def CreateRestClient():
    rc = RestClient(TETRATION_API_URL,
                    credentials_file=TETRATION_API_CRED_PATH, verify=False)
    return rc


'''
====================================================================================
Get Hosts with empty hostnames
------------------------------------------------------------------------------------
'''
def GetUnnamedHosts(rc,offset):
    req_payload = {
        "filter": {
            "type": "or",
            "filters": [
                {
                    "type": "eq",
                    "field": "hostname",
                    "value": ""
                },
                {
                    "type": "eq",
                    "field": "user_" + TETRATION_HOST_NAME_USER_ANNOTATION,
                    "value": ""
                }
            ]
        },
        "scopeName": TETRATION_SCOPE_NAME,
        "limit": TETRATION_SEARCH_LIMIT,
        "offset": offset if offset else ""
    }
    resp = rc.post('/inventory/search',json_body=json.dumps(req_payload))
    if resp.status_code != 200:
        print(resp.status_code)
        print(resp.text)
        exit(0)
    else:
        return resp.json()

'''
====================================================================================
Resolve empty hostnames by IP Address
------------------------------------------------------------------------------------
'''
def ResolveUnnamedHosts(inventoryList):
    resolved_hosts = []
    for host in inventoryList:
        try:
            addr = dns.reversename.from_address(host["ip"])
            host_name = str(resolver.query(addr,"PTR")[0])
            resolved_hosts.append({
                'IP': host['ip'],
                TETRATION_HOST_NAME_USER_ANNOTATION: host_name[:-1]
            })
        except:
            print("Couldn't resolve IP: {ip}".format(ip=host["ip"]))
            continue
    return resolved_hosts

'''
====================================================================================
Create annotation csv and push to Tetration
------------------------------------------------------------------------------------
'''
def SendAnnotationUpdates(rc,resolved_hosts):
    with open('annotations.csv', 'wb') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['IP', TETRATION_HOST_NAME_USER_ANNOTATION])
        writer.writeheader()
        writer.writerows(resolved_hosts)

    file_path = 'annotations.csv'
    req_payload = [tetpyclient.MultiPartOption(key='X-Tetration-Oper', val='add')]
    resp = rc.upload(file_path, '/assets/cmdb/upload/%s' % TETRATION_SCOPE_NAME, req_payload)
    if resp.status_code != 200:
        print("Error posting annotations to Tetration cluster")
    else:
        print("Successfully posted annotations to Tetration cluster")

def main():
    rc = CreateRestClient()
    offset = ''
    while True:
        print("Getting offset: {offset}".format(offset=offset))
        unnamed_hosts = GetUnnamedHosts(rc,offset)
        resolved_hosts = ResolveUnnamedHosts(unnamed_hosts["results"])
        SendAnnotationUpdates(rc,resolved_hosts)
        try:
            offset = unnamed_hosts["offset"]
        except:
            break
        time.sleep(2)

if __name__ == "__main__":
    main()
