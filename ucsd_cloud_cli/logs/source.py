import click
from .. import cf_data_dir
import yaml
import os

from troposphere import GetAtt, Ref, Join, Template, AccountId, Region, Output, Parameter
import troposphere.iam as iam


log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.group()
def cli():
    pass

@cli.group()
def source():
    pass

@source.command('generate')
def generate():
    t = Template()
    delivery_role_arn = t.add_parameter(Parameter('MasterAccountRoleARN',
        Type="String",
        Description="ARN of the Role created to allow CloudWatchLogs to dump logs to the log Kinesis stream"))
