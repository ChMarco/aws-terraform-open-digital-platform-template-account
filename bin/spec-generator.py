#!/usr/bin/env python


"""Account spec file generator.

Usage:
  spec-generator generate [options] <account_name> <account_email> <business_contact_email> <tech_contact_email>
  spec-generator report [options] <account_name> <account_email> <business_contact_email> <tech_contact_email>
  spec-generator (-h | --help)
  spec-generator --version

Modes of operation:
  generate                      Generators a new spec file based on params.
  report                        Prints a generated spec file based on params.

options:
  -h, --help                            Show this help message and exit.
  -o FILE. --output-file FILE           Output location of the generated spec file.
  --version                             Display version info and exit.
  -v, --verbose                         Log to activity to STDOUT at log level INFO.
  -d, --debug                           Increase log level to 'DEBUG'. Implies '--verbose'.

"""

from docopt import docopt
import jinja2
from utils import *
from validate_email import validate_email

OUTPUT_FILENAME = "output.yaml"
SPEC_TEMPLATE_FILE =  jinja2.Template("""
master_account_id: '599791326092'

default_domain: adidas-group.com

teams:
  - Name: application_account_{{ account_name }}
    BusinessContacts:
      - {{ business_contact_email }}
    TechnicalContacts:
      - {{ tech_contact_email }}

accounts:
  - Name: {{ account_name }}
    Email: {{ account_email }}
    Team: application_account_{{ account_name }}
    Template: https://github.com/contino/aws-terraform-open-digital-platform-template-account/tree/terraform

""")

def is_args_validate(log, args):
    is_valid = True
    #account_email
    if( not validate_email(args["<account_email>"])):
        log.error("Email entered is not valid: %s", args["<account_email>"])
        is_valid = False

    #account_name
    if(args["<account_name>"] is None):
        log.error("Account name is required.")
        is_valid = False

    #business_contact_email
    if(args["<business_contact_email>"] is None):
        log.error("Business contact email required.")
        is_valid = False

    #tech_contact_email
    if(args["<tech_contact_email>"] is None):
        log.error("Technical contact email required.")
        is_valid = False

    return is_valid


def main():
    args = docopt(__doc__, version='1.0')
    log = get_logger(args, os.path.basename(__file__).split('.')[0])

    #validate args
    log.debug("validating params...")
    if(not is_args_validate(log, args)):
        log.error("Args are not valid. Please check usage.")
        sys.exit(1)

    if args['generate']:
        #write rendered spec file to disk.
        filename = OUTPUT_FILENAME;

        if(args["--output-file"]):
            log.info("generating file: %s/%s", args["--output-file"], filename)
            filename = args["--output-file"] + "/" + OUTPUT_FILENAME

        with open(filename, "w") as yaml_file:
            yaml_file.write(SPEC_TEMPLATE_FILE.render(
                account_name = args["<account_name>"],
                account_email = args["<account_email>"],
                business_contact_email = args["<business_contact_email>"],
                tech_contact_email = args["<tech_contact_email>"]

            ))

    if args['report']:
        sys.stdout.write(SPEC_TEMPLATE_FILE.render(
                account_name = args["<account_name>"],
                account_email = args["<account_email>"],
                business_contact_email = args["<business_contact_email>"],
                tech_contact_email = args["<tech_contact_email>"]))

if __name__ == "__main__":
    main()