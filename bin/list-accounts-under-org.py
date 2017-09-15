#!/usr/bin/env python

import json
import logging
import os
import pprint
import boto3
from utils import get_root_account_id, get_logger


def list_accounts():
    log = get_logger(logging.INFO, os.path.basename(__file__).split('.')[0])

    #create the client
    org_client = boto3.client('organizations')
    pretty_printer = pprint.PrettyPrinter(indent=4)

    accounts = list()

    # get Id of root account
    full_account_list = org_client.list_accounts()['Accounts']
    root_account_ID = get_root_account_id(org_client)
    log.info("Using Root Id: %s", root_account_ID)

    # create local hash of account names and IDs. Do not include root account
    for account in full_account_list:
         if account['Id'] != root_account_ID:
             accounts.append(account)

    #remove joined timestamp as it causes JSON serialization issues.
    for element in accounts:
        del element['JoinedTimestamp']

    log.info("Found %s accounts.", accounts.__len__())
    #conver list to json and print to file.
    with open('../.artifacts/logs/accounts.json', 'wt') as out:
        json.dump(accounts, out)

    log.info(accounts)


def main():
    list_accounts()



if __name__ == "__main__":
    main()