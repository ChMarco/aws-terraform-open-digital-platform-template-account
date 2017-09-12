#!/usr/bin/env python

import pprint

import boto3
from utils import get_deployed_ou, get_deployed_policies, get_deployed_accounts, get_logger, get_root_org_id, \
    validate_spec_file


def enable_policy_type_in_root(org_client, root_id):
    """
    Ensure policy type 'SERVICE_CONTROL_POLICY' is enabled in the
    organization root.
    """
    p_type = org_client.describe_organization()['Organization']['AvailablePolicyTypes'][0]
    if (p_type['Type'] == 'SERVICE_CONTROL_POLICY' and p_type['Status'] != 'ENABLED'):
        org_client.enable_policy_type(RootId=root_id, PolicyType='SERVICE_CONTROL_POLICY')


def main():
    log = get_logger('--boto-log')

    #create the client
    org_client = boto3.client('organizations')
    root_id = get_root_org_id(org_client)
    pretty_printer = pprint.PrettyPrinter(indent=4)

    #scan account to see what has been deployed
    deployed = dict(
            policies = get_deployed_policies(org_client),
            accounts = get_deployed_accounts(log, org_client),
            ou = get_deployed_ou(org_client, root_id))

    pretty_printer.pprint(deployed)

    #read in organisation strcture
    print("Validating Organization spec file")
    org_spec = validate_spec_file(log, '../config/org-spec.yaml', 'org_spec')
    print("Spec Valid...")
    #TODO: do i need this?
    #enable_policy_type_in_root(org_client, root_id)

if __name__ == "__main__":
    main()
