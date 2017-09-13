#!/usr/bin/env python
import json

import pprint

import boto3
from utils import *


def enable_policy_type_in_root(org_client, root_id):
    """
    Ensure policy type 'SERVICE_CONTROL_POLICY' is enabled in the
    organization root.
    """
    p_type = org_client.describe_organization()['Organization']['AvailablePolicyTypes'][0]
    if (p_type['Type'] == 'SERVICE_CONTROL_POLICY' and p_type['Status'] != 'ENABLED'):
        org_client.enable_policy_type(RootId=root_id, PolicyType='SERVICE_CONTROL_POLICY')

def validate_accounts_unique_in_org(log, root_spec):
    """
    Ensure accounts are unique across org
    """
    # recursively build mapping of accounts to ou_names
    def map_accounts(spec, account_map={}):
        if 'Accounts' in spec and spec['Accounts']:
            for account in spec['Accounts']:
                if account in account_map:
                    account_map[account].append(spec['Name'])
                else:
                    account_map[account] = [(spec['Name'])]
        if 'Child_OU' in spec and spec['Child_OU']:
            for child_spec in spec['Child_OU']:
                map_accounts(child_spec, account_map)
        return account_map
    # find accounts set to more than one OU
    unique = True
    for account, ou in map_accounts(root_spec).items():
        if len(ou) > 1:
            log.error("Account '%s' set in multiple OU: %s" % (account, ou))
            unique = False
    if not unique:
        log.critical("Invalid org_spec: Do not assign accounts to multiple "
                "Organizatinal Units")
        print("Invalid org_spec... ")
        sys.exit(1)

def manage_policies(org_client, log, deployed, org_spec):
    """
    Manage Service Control Policies in the AWS Organization.  Make updates
    according to the sc_policies specification.  Do not touch
    the default policy.  Do not delete an attached policy.
    """
    for p_spec in org_spec['sc_policies']:
        policy_name = p_spec['Name']
        log.debug("considering sc_policy: %s" % policy_name)
        # dont touch default policy
        if policy_name == org_spec['default_policy']:
            continue
        policy = lookup(deployed['policies'], 'Name', policy_name)
        # delete existing sc_policy
        if ensure_absent(p_spec):
            if policy:
                log.info("Deleting policy '%s'" % (policy_name))
                # dont delete attached policy
                if org_client.list_targets_for_policy( PolicyId=policy['Id'])['Targets']:
                    log.error("Cannot delete policy '%s'. Still attached to OU" %
                            policy_name)
                else:
                    org_client.delete_policy(PolicyId=policy['Id'])
            continue
        # create or update sc_policy
        statement = dict(Effect=p_spec['Effect'], Action=p_spec['Actions'], Resource='*')
        policy_doc = json.dumps(dict(Version='2012-10-17', Statement=[statement]))
        log.debug("spec sc_policy_doc: %s" % policy_doc)
        # create new policy
        if not policy:
            log.info("Creating policy '%s'" % policy_name)
            org_client.create_policy(
                    Content=policy_doc,
                    Description=p_spec['Description'],
                    Name=p_spec['Name'],
                    Type='SERVICE_CONTROL_POLICY')
        # check for policy updates
        else:
            deployed_policy_doc = json.dumps(json.loads(org_client.describe_policy(
                    PolicyId=policy['Id'])['Policy']['Content']))
            log.debug("real sc_policy_doc: %s" % deployed_policy_doc)
            if (p_spec['Description'] != policy['Description']
                or policy_doc != deployed_policy_doc):
                log.info("Updating policy '%s'" % policy_name)
                org_client.update_policy(
                        PolicyId=policy['Id'],
                        Content=policy_doc,
                        Description=p_spec['Description'],)

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
    #TODO: do i need this and also should we check accounts exist?
    enable_policy_type_in_root(org_client, root_id)
    validate_master_id(org_client, org_spec)
    root_spec = lookup(org_spec['organizational_units'], 'Name', 'root')
    validate_accounts_unique_in_org(log, root_spec)
    managed = dict(
            accounts = search_spec(root_spec, 'Accounts', 'Child_OU'),
            ou = search_spec(root_spec, 'Name', 'Child_OU'),
            policies = [p['Name'] for p in org_spec['sc_policies']])
    # ensure default_policy is considered 'managed'
    if org_spec['default_policy'] not in managed['policies']:
        managed['policies'].append(org_spec['default_policy'])

    ###################### POLICY CRUD ######################
    #########################################################
    # all information is present now preform CRUD operations on policies
    manage_policies(org_client, log, deployed, org_spec)
    # rescan deployed policies
    deployed['policies'] = get_deployed_policies(org_client)



if __name__ == "__main__":
    main()
