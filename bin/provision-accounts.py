#!/usr/bin/env python

from aetypes import Enum
import base64
import json
import os
import sys
import boto3
import botocore
import time

class ACCOUNT_TYPE(Enum):
    audit = 'hello'
    logging = '../cloudformation/logging.template'
    global_services = 2
    iam_master = 3
    iam_user = 4
    security = 4

def getAccount_Type(account_name):
    if(account_name == "Logging Account"):
        return ACCOUNT_TYPE.logging
    elif(account_name == "Audit Account"):
        return ACCOUNT_TYPE.audit


def get_template(template_file):

    '''
        Read a template file and return the contents
    '''

    print("Reading resources from " + template_file)
    f = open(template_file, "r")
    cf_template = f.read()
    return cf_template

def configure_admin_user(session, account_id):
    """
    Configure an Administrator user with a strong password.
    """
    print "Creating IAM client..."
    iam = session.client("iam")
    print "Creating managed policy for protecting organization assets..."
    with open('../iam/pol_protect_organization_resources.json') as data_file:
        policy_document = json.load(data_file)
    iam.create_policy(
        PolicyName="ProtectedOrganizationResources",
        Description="Provides default-deny control over the Organization roles and resources that cannot be controlled through organization SCPs.",
        PolicyDocument=json.dumps(policy_document) % (account_id, account_id))
    time.sleep(10)
    print "Creating user..."
    iam.create_user(UserName="Administrator")
    print "Attached AWS managed AdministratorAccess policy..."
    iam.attach_user_policy(
        UserName="Administrator",
        PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess")
    iam.attach_user_policy(
        UserName="Administrator",
        PolicyArn="arn:aws:iam::%s:policy/ProtectedOrganizationResources" %
        account_id)
    # print "IAM user created and policies attached."

    password = base64.b64encode(os.urandom(32))
    iam.create_login_profile(
        UserName="Administrator",
        Password=password,
        PasswordResetRequired=True)
    print "IAM user password changed to:", password

def assume_role(account_id, account_role):

    '''
        Assume admin role within the newly created account and return credentials
    '''

    sts_client = boto3.client('sts')
    role_arn = 'arn:aws:iam::' + account_id + ':role/' + account_role

    # Call the assume_role method of the STSConnection object and pass the role
    # ARN and a role session name.

    assuming_role = True
    while assuming_role is True:
        try:
            assuming_role = False
            assumedRoleObject = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="NewAccountRole"
            )
        except botocore.exceptions.ClientError as e:
            assuming_role = True
            print(e)
            print("Retrying...")
            time.sleep(10)

    # From the response that contains the assumed role, get the temporary
    # credentials that can be used to make subsequent API calls
    return assumedRoleObject['Credentials']


def deploy_resources(session, account_json, stack_region):
    datestamp = time.strftime("%d/%m/%Y")

    print "Creating Cloudformation client..."
    cf_client = session.client('cloudformation')
    account_type = getAccount_Type(account_json['Name'])
    stack_name= account_json['Name'].replace(" ", "-").lower() + "-stack"
    print("Deploying resources from " + account_type + " as " + stack_name + " in " + stack_region)
    cf_template_json = get_template(account_type)

    #Validate the template. This will raise an exception if the template is invalid.
    print("Validating template before running...")
    cf_client.validate_template(TemplateBody=cf_template_json)
    print("Creating stack " + stack_name + " in " + stack_region)

    creating_stack = True
    while creating_stack is True:
        try:
            creating_stack = False
            create_stack_response = cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=cf_template_json,
                TimeoutInMinutes=10,
                Parameters=[
                    {
                        'ParameterKey' : 'pNotifyEmail',
                        'ParameterValue' : account_json['Email']
                    }
                ],
                NotificationARNs=[],
                Capabilities=[
                    'CAPABILITY_NAMED_IAM',
                ],
                OnFailure='DELETE',
                Tags=[
                    {
                        'Key': 'ManagedResource',
                        'Value': 'True'
                    },
                    {
                        'Key': 'DeployDate',
                        'Value': datestamp
                    }
                ]
            )
        except botocore.exceptions.ClientError as e:
            creating_stack = True
            print(e)
            print("Retrying...")
            time.sleep(10)

    stack_building = True
    print("Stack creation in process...")
    print(create_stack_response)
    while stack_building is True:
        event_list = cf_client.describe_stack_events(StackName=stack_name).get("StackEvents")
        stack_event = event_list[0]

        if (stack_event.get('ResourceType') == 'AWS::CloudFormation::Stack' and
           stack_event.get('ResourceStatus') == 'CREATE_COMPLETE'):
            stack_building = False
            print("Stack construction complete.")
        elif (stack_event.get('ResourceType') == 'AWS::CloudFormation::Stack' and
              stack_event.get('ResourceStatus') == 'ROLLBACK_COMPLETE'):
            stack_building = False
            print("Stack construction failed.")
            sys.exit(1)
        else:
            print(stack_event)
            print("Stack building . . .")
            time.sleep(10)

    stack = cf_client.describe_stacks(StackName=stack_name)
    return stack




def main():
    # read the accounts to provision
    with open('../.artifacts/logs/accounts.json') as data_file:
        data = json.load(data_file)

    #loop through all the accounts
    for account_json in data:
        #check status of account, if active proceed.
        if(account_json['Status'] == "ACTIVE"):
            #sts default role created when account was created
            print("Provisioning acount: " + account_json["Id"])
            credentials = assume_role(account_json["Id"], "OrganizationAccountAccessRole")
            print "Creating session..."
            session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"])
            print "Session created."
            configure_admin_user(session, account_json["Id"])
            deploy_resources(session, account_json, "eu-west-1")


if __name__ == '__main__':
    sys.exit(main())

