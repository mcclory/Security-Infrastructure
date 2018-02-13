from boto3
import hashlib
from . import VERSION

def _get_session(profile_name):
    """Centralized logic for handling getting a boto3 session for a given profile"""
    return boto3.Session(profile_name=profile_name)


def get_boto3_client(client_name, profile_name='default'):
    """Helper method for getting Boto3 client for a given profile"""
    session = _get_session(profile_name)
    return session.client(client_name)


def get_boto3_resource(resource_name, profile_name='default'):
    """Helper method for getting Boto3 resource for a given profile"""
    session = _get_session(profile_name)
    return session.resource(resource_name)


def get_profile_collection(security_account_profile_name):
    """Helper method for dealing with multiple accounts where a profile name for the centralized security logging account is passed in and the available profiles for use are put in a collection marked as 'child accounts'"""
    ret_val = {'sec_account': None, 'child_accounts': []}
    for profile in boto3.Session().get_profile_collection():
        if profile.lower() == security_account_profile_name.lower():
            ret_val['sec_account'] = profile
        else:
            ret_val['child_accounts'].append(profile)
    return ret_val


def serialize_template(template, description):
    """Commmon method for serializing a given template with the generator version, git sha and template md5 hash to validate consistency in debug scenarios."""
    template_hash = template.to_json()
    git_sha = ''
    description += ' |' + VERSION + '|' + template_hash + '|' + git_sha
    template.description = description
    return template
