import click
from .. import cf_data_dir
import yaml
import os

log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.group()
def target():
    pass

@target.command()
@click.option('--account_id', '-a', 'account_id_list', multiple=True)
@click.option('--bucket-name', '-b', 'bucket_name', envvar='BUCKETNAME')
@click.option('--log-file-prefix', 'log_file_prefix', '-p')
@click.option('--profile', '-p', 'aws_profile', envvar='AWS_PROFILE')
@click.option('--region', '-r', 'aws_region', envvar='AWS_REGION')
@click.option('--dry-run', 'dry_run', is_flag=True)
def initialize(account_id_list, bucket_name=None, log_file_prefix=None, aws_profile=None, aws_region=None, dry_run=False):
    """Logging target initializer that generates an appropriate CloudFormation template and then deploys it to create the necessary infrastructure for centralized security logging within the UCSD architecture."""
    template_name = 's3_log_target.yaml'
    with open (os.path.join(log_aggregation_cf, template_name), 'r') as f:
        cf_data = yaml.load(f.read())

    bucket_name = bucket_name if bucket_name else {'Ref': 'LogTargetS3Bucket'}
    log_file_prefix = log_file_prefix if log_file_prefix else ''
    aws_profile = aws_profile if aws_profile else 'default'
    aws_region = aws_region if aws_region else 'us-west-2'

    if 'Resources' in cf_data.keys():
        cf_data['Resources']['CloudwatchS3BucketPolicy'] = _generate_cloudwatch_bucket_policy(bucket_name, account_id_list, log_file_prefix)
    else:
        raise KeyError('CloudFormation template does not have the proper "Resources" section. Please check the %s template and try again' % template_name)

    cloudformation_template = yaml.dump(cf_data)

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
                                 'Resource':{
                                    "Fn::Join": [ ":", ["arn:aws:s3::", bucket_name]]}})
    ret_val['statement'].append({'Sid': 'AWSCloudTrailWrite20180208',
                                 'Effect': 'Allow',
                                 'Principal': {'Service': 'cloudtrail.amazonaws.com'},
                                 'Action': 's3:PutObject',
                                 'Resource': ['arn:aws:s3:::%s/%sAWSLogs/%s/*' % (bucket_name, log_file_prefix, account_id) for account_id in account_id_list],
                                 'Condition': {'StringEquals': {'s3:x-amz-acl': 'bucket-owner-full-control'}}})

    return ret_val

@click.group()
def account():
    pass

@click.group()
def service():
    pass

@account.command('add')
@click.option('--account-no', '-a', 'account_no')
def account_add(account_no):
    pass

@service.command('add')
@click.option('--service-name', 's', 'service_name')
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
