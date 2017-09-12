"""Utility functions used by the various scripts """
import logging
import os
import pkg_resources
import sys
import yaml


def load_validation_patterns(log):
    """
    Return dict of patterns for use when validating specification syntax
    """
    PATTERN_FILE = '../data/spec-validation-patterns.yaml'
    log.debug("loading file: '%s'" % PATTERN_FILE)
    filename =  os.path.abspath(pkg_resources.resource_filename(__name__, PATTERN_FILE))
            # __name__, '../data/spec-validation-patterns.yaml'))

    with open(filename) as f:
        return yaml.load(f.read())

def validate_spec_file(log, spec_file, pattern_name):
    '''
    Validate spec-file is properly formed.
    '''
    log.debug("loading spec file '%s'" % spec_file)
    validation_patterns = load_validation_patterns(log)
    with open(spec_file) as f:
        spec = yaml.load(f.read())
    log.debug("calling validate_spec() for pattern '%s'" % pattern_name)
    if validate_spec(log, validation_patterns, pattern_name, spec):
        return spec
    else:
        log.critical("Spec file '%s' failed syntax validation" % spec_file)
        sys.exit(1)

def get_template(template_file):

    '''
        Read a template file and return the contents
    '''

    print("Reading resources from " + template_file)
    f = open(template_file, "r")
    cf_template = f.read()
    return cf_template

def get_root_account_id(org_client):
    '''
    Query deployed AWS Organization for its Root ID.
    '''
    roots = org_client.list_roots()['Roots']
    if len(roots) >1:
        raise RuntimeError("org_client.list_roots returned multiple roots.")
        # get Id of root account
    root_account = org_client.list_roots()['Roots'][0]['Arn']
    return root_account.split(':')[4]

def get_root_org_id(org_client):
    '''
    Query deployed AWS Organization for its Root ID.
    '''
    roots = org_client.list_roots()['Roots']
    if len(roots) >1:
        raise RuntimeError("org_client.list_roots returned multiple roots.")
    return roots[0]['Id']

def get_deployed_accounts(log, org_client):
    '''
    Query AWS Organization for deployed accounts.
    Returns a list of dictionary.
    '''
    log.debug('running')
    accounts = org_client.list_accounts()
    deployed_accounts = accounts['Accounts']
    while 'NextToken' in accounts and accounts['NextToken']:
        log.debug("NextToken: %s" % accounts['NextToken'])
        accounts = org_client.list_accounts(NextToken=accounts['NextToken'])
        deployed_accounts += accounts['Accounts']
    # only return accounts that have an 'Name' key
    return [d for d in deployed_accounts if 'Name' in d ]
    return created_accounts


def get_deployed_policies(org_client):
    '''
    Return list of Service Control Policies deployed in Organization
    '''
    return org_client.list_policies(Filter='SERVICE_CONTROL_POLICY')['Policies']

def get_deployed_ou(org_client, root_id):
    '''
    Recursively traverse deployed AWS Organization.  Return list of
    organizational unit dictionaries.
    '''
    def build_deployed_ou_table(org_client, parent_name, parent_id, deployed_ou):
        # recusive sub function to build the 'deployed_ou' table
        child_ou = org_client.list_organizational_units_for_parent(
                ParentId=parent_id)['OrganizationalUnits']
        accounts = org_client.list_accounts_for_parent(
                ParentId=parent_id)['Accounts']
        if not deployed_ou:
            deployed_ou.append(dict(
                    Name = parent_name,
                    Id = parent_id,
                    Child_OU = [ou['Name'] for ou in child_ou if 'Name' in ou],
                    Accounts = [acc['Name'] for acc in accounts if 'Name' in acc]))
        else:
            for ou in deployed_ou:
                if ou['Name'] == parent_name:
                    ou['Child_OU'] = map(lambda d: d['Name'], child_ou)
                    ou['Accounts'] = map(lambda d: d['Name'], accounts)
        for ou in child_ou:
            ou['ParentId'] = parent_id
            deployed_ou.append(ou)
            build_deployed_ou_table(org_client, ou['Name'], ou['Id'], deployed_ou)
    # build the table
    deployed_ou = []
    build_deployed_ou_table(org_client, 'root', root_id, deployed_ou)
    return deployed_ou

def get_logger(args):
    """
    Setup logging.basicConfig from args.
    Return logging.Logger object.
    """
    # log level
    log_level = logging.CRITICAL
    # if args['--verbose'] or args['report'] or args['--boto-log']:
    #     log_level = logging.INFO
    # if args['--debug']:
    #     log_level = logging.DEBUG
    # log format
    log_format = '%(name)s: %(levelname)-9s%(message)s'
    # if args['report']:
    #     log_format = '%(message)s'
    # if args['--debug']:
    log_format = '%(name)s: %(levelname)-9s%(funcName)s():  %(message)s'
    # if (not args['--exec'] and not args['report']):
    #     log_format = '[dryrun] %s' % log_format
    # if not args['--boto-log']:
    logging.getLogger('botocore').propagate = False
    logging.getLogger('boto3').propagate = False
    logging.basicConfig(format=log_format, level=log_level)
    log = logging.getLogger(__name__)
    return log

def validate_spec(log, validation_patterns, pattern_name, spec):
    """
    Validate syntax of a given 'spec' dictionary against the
    named spec_pattern.
    """
    pattern = validation_patterns[pattern_name]
    valid_spec = True
    # test for required attributes
    required_attributes = [attr for attr in pattern if pattern[attr]['required']]
    for attr in required_attributes:
        if attr not in spec:
            log.error("Required attribute '%s' not found in '%s' spec. Context: %s" %
                    (attr, pattern_name, spec))
            valid_spec = False
    for attr in spec:
        log.debug("  considering attribute '%s'" % attr)
        # test if attribute is permitted
        if attr not in pattern:
            log.warn("Attribute '%s' does not exist in validation pattern '%s'" %
                    (attr, pattern_name))
            continue
        # handle recursive patterns
        if 'spec_pattern' in pattern[attr]:
            pattern_name = pattern[attr]['spec_pattern']
            if not isinstance(spec[attr], list):
                log.error("Attribute '%s' must be a list of '%s' specs.  Context: %s" %
                        (attr, pattern_name, spec))
                valid_spec = False
                continue
            for sub_spec in spec[attr]:
                log.debug("calling validate_spec() for pattern '%s'" % pattern_name)
                log.debug("context: %s" % sub_spec)
                if not validate_spec(log, validation_patterns, pattern_name, sub_spec):
                    valid_spec = False
        # test attribute type. ignore attr if value is None
        elif spec[attr]:
            spec_attr_type = spec[attr].__class__.__name__
            log.debug("    spec attribute object type: '%s'" % (spec_attr_type))
            # simple attribute pattern
            if isinstance(pattern[attr]['atype'], str):
                if spec_attr_type != pattern[attr]['atype']:
                    log.error("Attribute '%s' must be of type '%s'" %
                            (attr, pattern[attr]['atype']))
                    valid_spec = False
                    continue
            else:
                # complex attribute pattern
                valid_types = pattern[attr]['atype'].keys()
                log.debug("    pattern attribute types: '%s'" % valid_types)
                if not spec_attr_type in valid_types:
                    log.error("Attribute '%s' must be one of type '%s'" %
                            (attr, valid_types))
                    valid_spec = False
                    continue
                atype = pattern[attr]['atype'][spec_attr_type]
                # test attributes values
                if atype and 'values' in atype:
                    log.debug("    allowed values for attribute '%s': %s" %
                            (attr, atype['values']))
                    if not spec[attr] in atype['values']:
                        log.error("Value of attribute '%s' must be one of '%s'" %
                                (attr, atype['values']))
                        valid_spec = False
                        continue
    return valid_spec
