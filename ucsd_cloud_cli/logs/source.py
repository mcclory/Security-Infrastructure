import click
from .. import cf_data_dir
import yaml
import os

from troposphere import GetAtt, Ref, Join, Template, AccountId, Region, Output, Parameter
import troposphere.iam as iam
import troposphere.cloudtrail as ct
import troposphere.logs as cwl


log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.group()
def cli():
    pass

@cli.group()
def source():
    pass

@source.command('generate')
@click.option('--stream-arn', '-s', 'stream_arn', prompt='ARN of the Kinesis stream in the centrally managed account.' if os.getenv('CLI_PROMPT') else None)
@click.option('--role-arn', '-r', 'role_arn', prompt='ARN of the IAM Role for access to the centrally located Kinesis stream.' if os.getenv('CLI_PROMPT') else None)
@click.option('--dry-run', 'dry_run', is_flag=True, prompt='Dry Run' if os.getenv('CLI_PROMPT') else None)
def generate(stream_arn, role_arn, dry_run):
    t = Template()

    delivery_stream_arn = t.add_parameter(Parameter('MasterAccountDeliveryARN',
                                          Type="String",
                                          Description="ARN of the Kinesis stream to send logs to."))

    delivery_role_arn = t.add_parameter(Parameter('MasterAccountRoleARN',
                                        Type="String",
                                        Description="ARN of the Role created to allow CloudWatchLogs to dump logs to the log Kinesis stream"))

    cwl_group_retention = t.add_parameter(Parameter("LogGroupRetentionInDays",
        Type="Number",
        Description="Number of days to retain logs in the CloudWatch Log Group",
        MinValue=1,
        MaxValue=14,
        Default=1))

    cwl_group = t.add_resource(cwl.LogGroup('SecurityLogShippingGroup',
                               RetentionInDays=Ref(cwl_group_retention)))

    cwl_subscription = t.add_resource(cwl.SubscriptionFilter('SecurityLogShippingFilter',
                                      DestinationArn=Ref(delivery_stream_arn),
                                      RoleArn=Ref(delivery_role_arn),
                                      LogGroupName=Ref(cwl_group),
                                      FilterPattern="{$.userIdentity.type = Root}"))

     if dry_run:
         print(t.to_json())
     else:
         template_name = 'log_sources.json'
         with open (os.path.join(log_aggregation_cf, template_name), 'w') as f:
             f.write(t.to_json())
