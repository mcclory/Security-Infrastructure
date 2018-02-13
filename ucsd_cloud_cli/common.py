import boto3
import hashlib


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
    template_hash = hashlib.md5(json.dumps(template.to_json()).encode('utf-8')).hexdigest()
    description += ' |' + VERSION + '|' + template_hash
    template.description = description
    return template

def validate_tempalte(template_json):
    """Helper method to validate a given template if it was serialized via the serialize_template process (above). Intended to act as a means of validating a template's integrity from when it was first created"""
    template_dict = json.loads(template_json)
    if 'Description' in template_dict.keys():
        description = template_dict.pop('Description', None).split('|')
        template_hash = description[-1]
        version = description[-2]
        doc_hash = hashlib.md5(json.dumps(template_dict).encode('utf-8')).hexdigest()
        if doc_hash != template_hash:
            raise Error('Provided template (hash: %s) does not validate via included template hash (%s)' % (doc_hash, template_hash))
        else:
            return True
    else:
        print('No description to derive template hash from.')
        return False
