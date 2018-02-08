import click

SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.command()
def initialize():
    pass


def _generate_cloudwatch_bucket_policy(bucket_name, account_id_list):
    ret_val = {'Version': '2012-10-17'}
    ret_val['statement'] = []
    ret_val['statement'].append({'Sid': 'AWSCloudTrailACLCheck20131101',
                                 'Effect': 'Allow',
                                 'Principal': {
                                    'Service': 'cloudtrail.amazonaws.com'},
                                 'Action': 's3:GetBucketAcl',
                                 'Resource': 'arn:aws:s3:::%s' % bucket_name})

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
