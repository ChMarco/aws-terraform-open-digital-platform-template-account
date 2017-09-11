#!/usr/bin/env python

import json
import pprint
import boto3


def list_accounts():

    #create the client
    client = boto3.client('organizations')
    pretty_printer = pprint.PrettyPrinter(indent=4)

    accounts = list()
    response = client.list_accounts()

    # get Id of root account
    full_account_list = client.list_accounts()['Accounts']
    root_account = client.list_roots()['Roots'][0]['Arn']
    root_account_ID = root_account.split(':')[4]

    # create local hash of account names and IDs. Do not include root account
    for account in full_account_list:
         if account['Id'] != root_account_ID:
             accounts.append(account)

    #remove joined timestamp as it causes JSON serialization issues.
    for element in accounts:
        del element['JoinedTimestamp']

    #conver list to json and print to file.
    with open('../.artifacts/logs/accounts.json', 'wt') as out:
        json.dump(accounts, out)
    pretty_printer.pprint(accounts)


def main():
    list_accounts()



if __name__ == "__main__":
    main()