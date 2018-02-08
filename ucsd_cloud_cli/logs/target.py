import click

SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.command()
def initialize(account_id_list, bucket_name=None, log_file_prefix=None, dry_run=False):
    """Logging target initializer that generates an appropriate CloudFormation template and then deploys it to create the necessary infrastructure for centralized security logging within the UCSD architecture."""

    if dry_run:
        print(cloudformation_template)
    else:
        # perform calls to AWS and return results to stdout
        pass



def _generate_cloudwatch_bucket_policy(bucket_name, account_id_list, log_file_prefix = None):
    """Helper function to generate S3 bucket policies for a given list of account id's provided based on AWS documentation found here: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-set-bucket-policy-for-multiple-accounts.html

    Keyword arguments:
    bucket_name -- name of the bucket that this policy will be applied to
    account_id_list -- list of AWS Account ID's that should have access granted to put cloudtrail logs in the aforementioned bucket
    log_file_prefgix -- s3 key name prefix to insert into the AWS log 'path' when delivering log files to the referenced bucket from CloudWatch in the identified accounts
    """
    if log_file_prefix and not log_file_prefix.endswith('/'):
        log_file_prefix = log_file_prefix + '/'
    elif not log_file_prefix:
        log_file_prefix = ''

    ret_val = {'Version': '2012-10-17'}
    ret_val['statement'] = []
    ret_val['statement'].append({'Sid': 'AWSCloudTrailACLCheck20180208',
                                 'Effect': 'Allow',
                                 'Principal': {'Service': 'cloudtrail.amazonaws.com'},
                                 'Action': 's3:GetBucketAcl',
                                 'Resource': 'arn:aws:s3:::%s' % bucket_name})
    ret_val['statement'].append = {'Sid': 'AWSCloudTrailWrite20180208',
                                   'Effect': 'Allow',
                                   'Principal': {'Service': 'cloudtrail.amazonaws.com'},
                                   'Action': 's3:PutObject',
                                   'Resource': ['arn:aws:s3:::%s/%sAWSLogs/%s/*' % (bucket_name, log_file_prefix, account_id) for account_id in account_id_list],
                                   'Condition': {'StringEquals': {'s3:x-amz-acl': 'bucket-owner-full-control'}}}

    return ret_val

@click.group()
def account():
    pass

@click.group()
def service():
    pass

@account.command('add')
def account_add(account_no):
    pass

@service.command('add')
def add(service_name):
    if service_name.lower() not in SUPPORTED_SERVICES:
        raise NotImplementedError('Service %s is not implemented in this CLI' % service_name)
    pass


@account.command('remove')
def account_add(account_no):
    pass

@service.command('remove')
def service_remove(service_name):
    if service_name.lower() not in SUPPORTED_SERVICES:
        raise NotImplementedError('Service %s is not implemented in this CLI' % service_name)
    pass
