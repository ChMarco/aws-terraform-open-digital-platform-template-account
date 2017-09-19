#!/usr/bin/env python

import logging
import os
import boto3
import docopt as docopt
from utils import get_logger, get_root_org_id, get_deployed_accounts, lookup


def display_provisioned_accounts(log, deployed_accounts):
    """
    Print report of currently deployed accounts in AWS Organization.
    """
    header = "Provisioned Accounts in Org:"
    overbar = '_' * len(header)
    log.info("\n%s\n%s" % (overbar, header))
    for a_name in sorted([a['Name'] for a in deployed_accounts]):
        a_id = lookup(deployed_accounts, 'Name', a_name, 'Id')
        a_email = lookup(deployed_accounts, 'Name', a_name, 'Email')
        spacer = ' ' * (24 - len(a_name))
        log.info("%s%s%s\t\t%s" % (a_name, spacer, a_id, a_email))

def main():
    log = get_logger(logging.INFO, os.path.basename(__file__).split('.')[0])
    args = docopt(__doc__)
    #create the client
    org_client = boto3.client('organizations')
    root_id = get_root_org_id(org_client)
    deployed_accounts = get_deployed_accounts(log, org_client)

    display_provisioned_accounts(log, deployed_accounts)

if __name__ == "__main__":
    main()