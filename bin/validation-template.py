#!/usr/bin/env python

import boto3
from utils import get_template


def validate_cloudformtion_template(cf_template_json):
    #create the client
    cf_client = boto3.client('cloudformation')
    #Validate the template. This will raise an exception if the template is invalid.
    cf_client.validate_template(TemplateBody=cf_template_json)


def main():
    template = get_template('../cloudformation/logging.template')
    validate_cloudformtion_template(template)



if __name__ == "__main__":
    main()

