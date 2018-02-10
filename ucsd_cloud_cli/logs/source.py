import click
import yaml
import os

data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'data')
cf_data_dir = os.path.join(data_dir, 'cloudformation')

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
@click.option('--dry-run', 'dry_run', is_flag=True, prompt='Dry Run' if os.getenv('CLI_PROMPT') else None, help="boolean indicates whether template should be printed to screen vs. being saved to file")
def generate(dry_run):
    """CloudFormation template generator to apply to all accounts which configures log sources to publish to the centralized log target(s) specified"""
    t = Template()

    #
    # CloudWatch Logs setup - Set up shipping to 'centralized' account
    #

        # Parameters
    delivery_stream_arn = t.add_parameter(Parameter('MasterAccountDeliveryARN',
                                          Type="String",
                                          Default="",
                                          Description="ARN of the Kinesis stream to send logs to."))

    delivery_role_arn = t.add_parameter(Parameter('MasterAccountRoleARN',
                                        Type="String",
                                        Default="",
                                        Description="ARN of the Role created to allow CloudWatchLogs to dump logs to the log Kinesis stream"))

        # resources
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

        # outputs
    t.add_output(Output('CloudWatchLogGroup',
                 Value=GetAtt(cwl_group, "Arn"),
                 Description="ARN of the CloudWatch Log Group created to flow logs to the centralized logging stream."))

    #
    # CloudTrail setup - ship to S3 in 'central account' as well as cloudtrail logs if it'll let us :)
    #

        # parameters
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

        # resources
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

        # outputs
    t.add_output(Output('CloudTrailARN',
                        Description="ARN of the CloudTrail Trail configured for this log source deployment.",
                        Value=GetAtt(ct_trail, "Arn")))

    if dry_run:
        print(t.to_json())
    else:
        template_name = 'log_sources.json'
        with open (os.path.join(log_aggregation_cf, template_name), 'w') as f:
            f.write(t.to_json())
