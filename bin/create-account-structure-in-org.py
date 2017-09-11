#!/usr/bin/env python

import json
import sys
import boto3
import botocore
import time


def create_account(
        account_name,
        account_email,
        account_role,
        access_to_billing,
        organization_unit_id,
        scp):

    '''
        Create a new AWS account and add it to an organization
    '''

    client = boto3.client('organizations')
    try:
        create_account_response = client.create_account(Email=account_email, AccountName=account_name,
                                                        RoleName=account_role,
                                                        IamUserAccessToBilling=access_to_billing)
    except botocore.exceptions.ClientError as e:
        print(e)
        sys.exit(1)

    time.sleep(10)

    account_status = 'IN_PROGRESS'
    while account_status == 'IN_PROGRESS':
        create_account_status_response = client.describe_create_account_status(
            CreateAccountRequestId=create_account_response.get('CreateAccountStatus').get('Id'))
        print("Create account status "+str(create_account_status_response))
        account_status = create_account_status_response.get('CreateAccountStatus').get('State')
    if account_status == 'SUCCEEDED':
        account_id = create_account_status_response.get('CreateAccountStatus').get('AccountId')
    elif account_status == 'FAILED':
        print("Account creation failed: " + create_account_status_response.get('CreateAccountStatus').get('FailureReason'))
    root_id = client.list_roots().get('Roots')[0].get('Id')

    # Move account to the org
    if organization_unit_id is not None:
        try:
            describe_organization_response = client.describe_organizational_unit(
                OrganizationalUnitId=organization_unit_id)
            move_account_response = client.move_account(AccountId=account_id, SourceParentId=root_id,
                                                        DestinationParentId=organization_unit_id)
        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r} "
            message = template.format(type(ex).__name__, ex.args)
            # create_organizational_unit(organization_unit_id)
            print(message)

    # Attach policy to account if exists
    if scp is not None:
        attach_policy_response = client.attach_policy(PolicyId=scp, TargetId=account_id)
        print("Attach policy response "+str(attach_policy_response))


def main():
    # read the account structure
    with open('../config/create-account.json') as data_file:
        data = json.load(data_file)

    for json_dict in data:
        for key,value in json_dict.iteritems():
            # create each account
            create_account(value["accountName"], value["email"], value["iamRoleName"], value["IamUserAccessToBilling"], None, None)



if __name__ == '__main__':
    sys.exit(main())