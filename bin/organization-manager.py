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

def get_parent_id(org_client, account_id):
    """
    Query deployed AWS organanization for 'account_id. Return the 'Id' of
    the parent OrganizationalUnit or 'None'.
    """
    parents = org_client.list_parents(ChildId=account_id)['Parents']
    try:
        len(parents) == 1
        return parents[0]['Id']
    except:
        raise RuntimeError("API Error: account '%s' has more than one parent: "
                % (account_id, parents))

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

def place_unmanged_accounts(org_client, log, deployed, account_list, dest_parent):
    """
    Move any unmanaged accounts into the default OU.
    """
    for account in account_list:
        account_id = lookup(deployed['accounts'], 'Name', account, 'Id')
        dest_parent_id   = lookup(deployed['ou'], 'Name', dest_parent, 'Id')
        source_parent_id = get_parent_id(org_client, account_id)
        if dest_parent_id and dest_parent_id != source_parent_id:
            log.info("Moving unmanged account '%s' to default OU '%s'" % (account, dest_parent))
            org_client.move_account(AccountId=account_id, SourceParentId=source_parent_id,
                                    DestinationParentId=dest_parent_id)


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

def manage_ou(org_client, log, deployed, org_spec, ou_spec_list, parent_name):
    """
    Recursive function to manage OrganizationalUnits in the AWS
    Organization.
    """
    for ou_spec in ou_spec_list:
        # ou exists
        ou = lookup(deployed['ou'], 'Name', ou_spec['Name'])
        if ou:
            # check for child_ou. recurse before other tasks.
            if 'Child_OU' in ou_spec:
                manage_ou(org_client, log, deployed, org_spec, ou_spec['Child_OU'], ou_spec['Name'])
            # check if ou 'absent'
            if ensure_absent(ou_spec):
                log.info("Deleting OU %s" % ou_spec['Name'])
                # error if ou contains anything
                error_flag = False
                for key in ['Accounts', 'SC_Policies', 'Child_OU']:
                    if key in ou and ou[key]:
                        log.error("Can not delete OU '%s'. deployed '%s' exists." % (ou_spec['Name'], key))
                        error_flag = True
                if error_flag:
                    continue
                else:
                    org_client.delete_organizational_unit(OrganizationalUnitId=ou['Id'])
            # manage account and sc_policy placement in OU
            else:
                manage_policy_attachments(org_client, log, deployed, org_spec, ou_spec, ou['Id'])
                manage_account_moves(org_client, log, deployed, ou_spec, ou['Id'])
        # create new OU
        elif not ensure_absent(ou_spec):
            log.info("Creating new OU '%s' under parent '%s'" % (ou_spec['Name'], parent_name))
            new_ou = org_client.create_organizational_unit(ParentId=lookup(deployed['ou'],'Name',parent_name,'Id'),
                    Name=ou_spec['Name'])['OrganizationalUnit']
            # account and sc_policy placement
            manage_policy_attachments(org_client, log, deployed, org_spec, ou_spec, new_ou['Id'])
            manage_account_moves(org_client, log, deployed, ou_spec, new_ou['Id'])
            # recurse if child OU
            if ('Child_OU' in ou_spec and isinstance(new_ou, dict) and 'Id' in new_ou):
                manage_ou(org_client, log, deployed, org_spec, ou_spec['Child_OU'], new_ou['Name'])

def manage_account_moves(org_client, log, deployed, ou_spec, dest_parent_id):
    """
    Alter deployed AWS Organization.  Ensure accounts are contained
    by designated OrganizationalUnits based on OU specification.
    """
    if 'Accounts' in ou_spec and ou_spec['Accounts']:
        for account in ou_spec['Accounts']:
            account_id = lookup(deployed['accounts'], 'Name', account, 'Id')
            if not account_id:
                log.warn("Account '%s' not yet in Organization" % account)
            else:
                source_parent_id = get_parent_id(org_client, account_id)
                if dest_parent_id != source_parent_id:
                    log.info("Moving account '%s' to OU '%s'" % (account, ou_spec['Name']))
                    org_client.move_account(AccountId=account_id, SourceParentId=source_parent_id,
                                DestinationParentId=dest_parent_id)

def manage_policy_attachments(org_client, log, deployed, org_spec, ou_spec, ou_id):
    """
    Attach or detach specified Service Control Policy to a deployed
    OrganizatinalUnit.  Do not detach the default policy ever.
    """
    # create lists policies_to_attach and policies_to_detach
    attached_policy_list = list_policies_in_ou(org_client, ou_id)
    if 'SC_Policies' in ou_spec and isinstance(ou_spec['SC_Policies'], list):
        spec_policy_list = ou_spec['SC_Policies']
    else:
        spec_policy_list = []
    policies_to_attach = [p for p in spec_policy_list
            if p not in attached_policy_list]
    policies_to_detach = [p for p in attached_policy_list
            if p not in spec_policy_list
            and p != org_spec['default_policy']]
    # attach policies
    for policy_name in policies_to_attach:
        if not lookup(deployed['policies'],'Name',policy_name):
            raise RuntimeError("spec-file: ou_spec: policy '%s' not defined" %
                    policy_name)
        if not ensure_absent(ou_spec):
            log.info("Attaching policy '%s' to OU '%s'" % (policy_name, ou_spec['Name']))
            org_client.attach_policy(PolicyId=lookup(deployed['policies'], 'Name', policy_name, 'Id'), TargetId=ou_id)
    # detach policies
    for policy_name in policies_to_detach:
        log.info("Detaching policy '%s' from OU '%s'" % (policy_name, ou_spec['Name']))
        org_client.detach_policy(PolicyId=lookup(deployed['policies'], 'Name', policy_name, 'Id'), TargetId=ou_id)

def main():
    log = get_logger(logging.INFO)

    #create the client
    org_client = boto3.client('organizations')
    root_id = get_root_org_id(org_client)
    pretty_printer = pprint.PrettyPrinter(indent=4)

    #scan account to see what has been deployed
    deployed = dict(
            policies = get_deployed_policies(org_client),
            accounts = get_deployed_accounts(log, org_client),
            ou = get_deployed_ou(org_client, root_id))

    #read in organisation strcture
    log.info("Validating Organization spec file")
    org_spec = validate_spec_file(log, '../config/org-spec.yaml', 'org_spec')
    log.info("Spec Valid...")
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

    ######################## OU CRUD ########################
    #########################################################
    manage_ou(org_client, log, deployed, org_spec, org_spec['organizational_units'], 'root')

    ######################## CLEAN UP #######################
    #########################################################
     # check for unmanaged resources
    for key in managed.keys():
        unmanaged= [a['Name'] for a in deployed[key] if a['Name'] not in managed[key]]
        if unmanaged:
            log.warn("Unmanaged %s in Organization: %s" % (key,', '.join(unmanaged)))
            if key ==  'accounts':
                # append unmanaged accounts to default_ou
                place_unmanged_accounts(org_client, log, deployed, unmanaged, org_spec['default_ou'])

if __name__ == "__main__":
    main()
