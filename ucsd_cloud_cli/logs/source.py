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
    stream_arn = stream_arn if stream_arn else ""
    role_arn = role_arn if role_arn else ""

    t = Template()

    #
    # CloudWatch Logs setup
    #
    delivery_stream_arn = t.add_parameter(Parameter('MasterAccountDeliveryARN',
                                          Type="String",
                                          Default=stream_arn,
                                          Description="ARN of the Kinesis stream to send logs to."))

    delivery_role_arn = t.add_parameter(Parameter('MasterAccountRoleARN',
                                        Type="String",
                                        Default=role_arn,
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

    t.add_output(Output('CloudWatchLogGroup',
                 Value=GetAtt(cwl_group, "Arn"),
                 Description="ARN of the CloudWatch Log Group created to flow logs to the centralized logging stream."))

    #
    # CloudTrail setup
    #
    ct_is_logging = t.add_parameter(Parameter('CloudTrailIsLogging',
                                    Type="Boolean",
                                    Default=True,
                                    Description="Flag indicating that CloudTrail is configured to send logs."))

    ct_include_global = t.add_parameter(Parameter('CloudTrailIncludeGlobal',
                                        Type="Boolean",
                                        Default=True,
                                        Description="Flag indicating that CloudTrail is configured to capture global service events."))
    ct_multi_region = t.add_parameter(Parameter('CloudTrailMultiRegion',
                                      Type="Boolean",
                                      Default=True,
                                      Description="Flag indicating that CloudTrail is to be configured in multi-region mode"))

    ct_s3_bucket = t.add_parameter(Parameter('CloudTrailBucketName',
                                   Type='String',
                                   Description='Name of the S3 bucket to ship logs to in the centralized aggregation account.'))

    ct_s3_key_prefix = t.add_parameter(Parameter('CloudTrailKeyPrefix',
                                        Type='String',
                                        Default='',
                                        Description='Key name prefix for logs being sent to S3'))

    ct_trail = t.add_resource(ct.Trail(
                              "SecurityTrail",
                              TrailName=Join("-", ["SecurityTrail", Region]),
                              CloudWatchLogsLogGroupArn=Ref(delivery_stream_arn),
                              CloudWatchLogsRoleArn=Ref(delivery_role_arn),
                              S3BucketName=Ref(ct_s3_bucket),
                              S3KeyPrefix=Ref(ct_s3_key_prefix),
                              IncludeGlobalServiceEvents=Ref(ct_include_global),
                              IsMultiRegionTrail=Ref(ct_multi_region),
                              IsLogging=Ref(ct_is_logging)))

    t.add_output(Output('CloudTrailARN',
                        Description="ARN of the CloudTrail Trail configured for this log source deployment.",
                        Value=GetAtt(ct_trail, "Arn")))

    if dry_run:
        print(t.to_json())
    else:
        template_name = 'log_sources.json'
        with open (os.path.join(log_aggregation_cf, template_name), 'w') as f:
            f.write(t.to_json())
