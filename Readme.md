
AWS Organizations Structure :: Open Digital Platform
========================================================

Overview
--------
A structured approach to consuming AWS as a platform is needed to ensure proper controls are in place regarding security, billing, operational management and architectural strategy.
This project provisions best practices for Adidas Organisation structures within Amazon Web Services (AWS) Organizations. 
The objective of these scripts is to template the creation of Adidas AWS global account structure. It provides three python executables:

- **account-manager.py** Manage accounts in an AWS Organization.
- **organization-manager.py** Manage recources in an AWS Organization.
- **spec-generator.py** Generates new account spec files based on commandline inputs. 

How it works
------------
**Before Running...**
* The script will authenticate with AWS by looking for ``~/.aws/credentials``


**How to run**

**Docker Build**
```docker build . -t <<BUILD_NAME>>:latest```


Usage::
-------

#### External usage (non Docker image)
* Ensure ``$HOME/.aws/`` store the appropriate credentials to your environment. Please see [Boto 3 Configuration](http://boto3.readthedocs.io/en/latest/guide/configuration.html)

###### Running manually with Python (2.7)

  # Run each command with -h option for full usage info.

  organization-manager.py report
  organization-manager.py organization -v -s org-spec.yaml [--exec]

  spec-generator.py report
  spec-generator.py generate 

  account-manger.py report
  account-manger.py create -v -s account-spec.yaml [--exec]



