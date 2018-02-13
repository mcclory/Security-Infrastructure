import click
import yaml
import os

data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'data')
cf_data_dir = os.path.join(data_dir, 'cloudformation')

from troposphere import GetAtt, Ref, Join, Template, AccountId, Region, Output, Parameter
import troposphere.iam as iam
import troposphere.cloudtrail as ct
import troposphere.logs as cwl
import troposphere.ec2 as ec2

from awacs.aws import Allow, Statement, Principal, Policy
from awacs.logs import CreateLogGroup, CreateLogStream, PutLogEvents, DescribeLogGroups, DescribeLogStreams
from awacs.iam import PassRole as IAMPassRole
from awacs.sts import AssumeRole

log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

security_log_shipping_group_name = "SecurityLogShippingGroup"

@click.group()
def cli():
    pass

@cli.group()
def source():
    """Command group pertaining to the management of CloudFormation templates designed to configure AWS accounts to ship logs to a target AWS account configured to aggregate infrastructure-level logs."""
    pass


@source.command()
@click.option('--dry-run', 'dry_run', is_flag=True, prompt='Dry Run' if os.getenv('CLI_PROMPT') else None, help="boolean indicates whether template should be printed to screen vs. being saved to file")
@click.option('--file', '-f', 'file_location', type=click.Path(), prompt="Save file path" if os.getenv('CLI_PROMPT') else None, help="Specific path to save the generated template in. If not specifies, defaults to package data directory.")
def flow_log():
    """Method generates a mini-template for use in configuring VPC Flow Log configuration within an account. This template should apply to all VPCs in all regions for any account that's configured as a log 'sender' and aggregates logs via the previously created CloudWatch Logs group (to be supplied as a Parameter)."""

    t = Template()
    delivery_logs_permission_arn = t.add_parameter(Parameter('DeliveryLogsPermissionArn',
                                    Type="String",
                                    Description="The Amazon Resource Name (ARN) of an AWS Identity and Access Management (IAM) role that permits Amazon EC2 to publish flow logs to a CloudWatch Logs log group in your account. - Provided by the outputs of the child account-level central configuration."))

    # This parameter should be mapped to the 'CloudWatchLogGroupName' output in the template created by the generate() method below
    # we've abstracted the name to a variable and set the default here consistent with what the parent CFn template is setting in the child account configuration
    log_group_name = t.add_parameter(Parameter('LogGroupName',
                                    Type="String",
                                    Default=security_log_shipping_group_name,
                                    Description="The name of a new or existing CloudWatch Logs log group where Amazon EC2 publishes your flow logs. - Provided by the outputs of the child account-level central configuration - output name: CloudWatchLogGroupName."))

    vpc_id = t.add_parameter(Parameter('VPCId',
                             Type="AWS::EC2::VPC::Id",
                             Description="The ID of an existing VPC within the region *this* CloudFormation template is being deployed within that should have its corresponding VPC Flow Logs transmitted to the Log Group identified by LogGroupName."))

    traffic_type = t.add_parameter(Parameter('TrafficType',
                                   Type="String",
                                   Default="ALL",
                                   AllowedValues=["ACCEPT", "REJECT", "ALL"],
                                   Description="The type of traffic to log."))

    vpc_flow_log = t.add_resource(ec2.FlowLog('vpc_flow_log',
                                  ResourceId=Ref(vpc_id),
                                  DeliveryLogsPermissionArn=Ref(delivery_logs_permission_arn),
                                  ResourceType="VPC",
                                  LogGroupName=Ref(log_group_name),
                                  TrafficType=Ref(traffic_type)))

@source.command('generate')
@click.option('--dry-run', 'dry_run', is_flag=True, prompt='Dry Run' if os.getenv('CLI_PROMPT') else None, help="boolean indicates whether template should be printed to screen vs. being saved to file")
@click.option('--file', '-f', 'file_location', type=click.Path(), prompt="Save file path" if os.getenv('CLI_PROMPT') else None, help="Specific path to save the generated template in. If not specifies, defaults to package data directory.")
def generate(dry_run, file_location=None):
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
                               LogGroupName=security_log_shipping_group_name,
                               RetentionInDays=Ref(cwl_group_retention)))

    cwl_subscription = t.add_resource(cwl.SubscriptionFilter('SecurityLogShippingFilter',
                                      DestinationArn=Ref(delivery_stream_arn),
                                      RoleArn=Ref(delivery_role_arn),
                                      LogGroupName=Ref(cwl_group),
                                      FilterPattern="{$.userIdentity.type = Root}"))

    # Create IAM role to allow VPC Flow Logs within this account to push data to CloudWatch Logs per https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/flow-logs.html#flow-logs-iam
    vpc_flow_log_iam_role = t.add_resource(iam.Role('VPCFlowLogToCWLIAMRole',
                                           AssumeRolePolicyDocument=Policy(
                                               Statement=[Statement(Effect=Allow, Action=[AssumeRole], Principal=Principal("Service", "vpc-flow-logs.amazonaws.com"))])))

    vpc_flow_log_policies = t.add_resource(iam.PolicyType('VPCFlowLogToCWLPolicy',
                                           PolicyName='vpcflowlogtocwlpolicy20180213',
                                           Roles=[Ref(vpc_flow_log_iam_role)],
                                           PolicyDocument=Policy(
                                                Statement=[
                                                    Statement(
                                                        Effect=Allow,
                                                        Action=[CreateLogGroup, CreateLogStream, PutLogEvents, DescribeLogGroups, DescribeLogStreams],
                                                        Resource=["*"])])))

        # outputs
    t.add_output(Output('CloudWatchLogGroupName',
                 Value=Ref(cwl_group),
                 Description="Name of the CloudWatch Log Group created to flow logs to the centralized logging stream."))

    t.add_output(Output('CloudWatchLogGroupARN',
                 Value=GetAtt(cwl_group, "Arn"),
                 Description="ARN of the CloudWatch Log Group created to flow logs to the centralized logging stream."))

    t.add_output(Output('VPCFlowLogDeliveryLogsPermissionArn',
                 Value=GetAtt(vpc_flow_log_iam_role, "Arn"),
                 Description="ARN of the IAM role for VPC Flow Logs to use within this account to ship VPC flow logs through."))


    #
    # CloudTrail setup - ship to S3 in 'central account' as well as cloudtrail logs if it'll let us :)
    #

        # parameters
    ct_is_logging = t.add_parameter(Parameter('CloudTrailIsLogging',
                                    Type="String",
                                    Default="false",
                                    AllowedValues=["true", "false"],
                                    Description="Flag indicating that CloudTrail is configured to send logs."))

    ct_include_global = t.add_parameter(Parameter('CloudTrailIncludeGlobal',
                                        Type="String",
                                        Default="true",
                                        AllowedValues=["true", "false"],
                                        Description="Flag indicating that CloudTrail is configured to capture global service events."))

    ct_multi_region = t.add_parameter(Parameter('CloudTrailMultiRegion',
                                      Type="String",
                                      Default="true",
                                      AllowedValues=["true", "false"],
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
        save_path = file_location if file_location else os.path.join(log_aggregation_cf, 'log_sources.json')
        with open (save_path, 'w') as f:
            f.write(t.to_json())
