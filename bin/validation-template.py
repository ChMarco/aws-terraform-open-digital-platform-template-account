
#!/usr/bin/env python
import boto3


def get_template(template_file):

    '''
        Read a template file and return the contents
    '''

    print("Reading resources from " + template_file)
    f = open(template_file, "r")
    cf_template = f.read()
    return cf_template


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

