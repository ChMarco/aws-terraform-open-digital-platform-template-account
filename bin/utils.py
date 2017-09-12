"""Utility functions used by the various scripts """


def get_root_id(org_client):
    """
    Query deployed AWS Organization for its Root ID.
    """
    roots = org_client.list_roots()['Roots']
    if len(roots) >1:
        raise RuntimeError("org_client.list_roots returned multiple roots.")
        # get Id of root account
    root_account = org_client.list_roots()['Roots'][0]['Arn']
    return root_account.split(':')[4]