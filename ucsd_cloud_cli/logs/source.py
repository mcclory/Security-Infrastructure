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
def generate():
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
