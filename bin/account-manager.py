#!/usr/bin/env python

"""Manage accounts in an AWS Organization.

Usage:
  awsaccounts report [-d] [--boto-log]
  awsaccounts create (--spec-file FILE) [--exec] [-vd] [--boto-log]
  awsaccounts (-h | --help)
  awsaccounts --version

Modes of operation:
  report         Display organization status report only.
  create         Create new accounts in AWS Org per specifation.

Options:
  -h, --help                 Show this help message and exit.
  --version                  Display version info and exit.
  -s FILE, --spec-file FILE  AWS account specification file in yaml format.
  --exec                     Execute proposed changes to AWS accounts.
  -v, --verbose              Log to activity to STDOUT at log level INFO.
  -d, --debug                Increase log level to 'DEBUG'. Implies '--verbose'.
  --boto-log                 Include botocore and boto3 logs in log stream.

"""

import logging
import os
import boto3
from docopt import docopt
from utils import get_logger, get_root_org_id, get_deployed_accounts, lookup, validate_spec_file, validate_master_id


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
    args = docopt(__doc__)
    logging_level = logging.INFO
    if args['--debug']:
        logging_level = logging.DEBUG

    log = get_logger(logging_level, os.path.basename(__file__).split('.')[0])


    #create the client
    org_client = boto3.client('organizations')
    root_id = get_root_org_id(org_client)
    deployed_accounts = get_deployed_accounts(log, org_client)

    if args['--spec-file']:
        account_spec = validate_spec_file(log, args['--spec-file'], 'account_spec')
        validate_master_id(org_client, account_spec)


    if args['report']:
        display_provisioned_accounts(log, deployed_accounts)

if __name__ == "__main__":
    main()