import click
import json
import os

data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'data')
cf_data_dir = os.path.join(data_dir, 'cloudformation')

from troposphere import GetAtt, Ref, Join, Template, AccountId, Region, Output, Parameter
import troposphere.iam as iam
import troposphere.s3 as s3
import troposphere.cloudtrail as ct
import troposphere.logs as cwl
import troposphere.kinesis as k
import troposphere.sqs as sqs
import troposphere.sns as sns
import troposphere.firehose as fh

from awacs.aws import Allow, Statement, Principal, Policy, Condition, StringEquals, ArnLike
from awacs.kinesis import PutRecord as KinesisPutRecord
from awacs.iam import PassRole as IAMPassRole
from awacs.sts import AssumeRole
from awacs.s3 import GetBucketAcl, PutObject
import awacs.sqs as asqs
import awacs.ec2 as aec2
import awacs.awslambda as al
import awacs.kinesis as akinesis
import awacs.kms as akms
import awacs.sts as asts
import awacs.rds as ards
import awacs.cloudfront as acf
import awacs.cloudwatch as acw
import awacs.elasticloadbalancing as aelb
import awacs.inspector as ainspector
import awacs.sns as asns
import awacs.logs as alogs
import awacs.config as aconfig
import awacs.s3 as as3
import awacs.iam as aiam
import awacs.autoscaling as aas

log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.group()
def cli():
    pass


@cli.group()
def target():
    """Command group pertaining to the management of CloudFormation templates designed to configure the AWS account where infrastructure-level logging is aggregated to."""
    pass

def _generate_splunk_policy(policy_name='splunkAllAccessPolicy', roles=[], users=[]):
    """Helper method to encapsulate the complexity of generating the 'all-in-one' policy document for Splunk AWS Plugin per http://docs.splunk.com/Documentation/AddOns/released/AWS/ConfigureAWSpermissions#Configure_one_policy_containing_permissions_for_all_inputs"""
    return iam.PolicyType(policy_name,
        PolicyName="%s20180224" % policy_name,
        Roles=roles,
        Users=users,
        PolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[asqs.GetQueueAttributes, asqs.ListQueues, asqs.ReceiveMessage, asqs.GetQueueUrl, asqs.SendMessage, asqs.DeleteMessage,
                            as3.ListBucket, as3.GetObject, as3.GetBucketLocation, as3.ListAllMyBuckets, as3.GetBucketTagging, as3.GetAccelerateConfiguration, as3.GetBucketLogging, as3.GetLifecycleConfiguration, as3.GetBucketCORS,
                            aconfig.DeliverConfigSnapshot, aconfig.DescribeConfigRules, aconfig.DescribeConfigRuleEvaluationStatus, aconfig.GetComplianceDetailsByConfigRule, aconfig.GetComplianceSummaryByConfigRule,
                            aiam.GetUser, aiam.ListUsers, aiam.GetAccountPasswordPolicy, aiam.ListAccessKeys, aiam.GetAccessKeyLastUsed,
                            aas.Action('Describe*'),
                            acw.Action('Describe*'), acw.Action('Get*'), acw.Action('List*'),
                            asns.Action('Get*'), asns.Action('List*'), asns.Publish,
                            alogs.DescribeLogGroups, alogs.DescribeLogStreams, alogs.GetLogEvents,
                            aec2.DescribeInstances, aec2.DescribeReservedInstances, aec2.DescribeSnapshots, aec2.DescribeRegions, aec2.DescribeKeyPairs, aec2.DescribeNetworkAcls, aec2.DescribeSecurityGroups, aec2.DescribeSubnets, aec2.DescribeVolumes, aec2.DescribeVpcs, aec2.DescribeImages, aec2.DescribeAddresses,
                            al.ListFunctions,
                            ards.DescribeDBInstances,
                            acf.ListDistributions,
                            aelb.DescribeLoadBalancers, aelb.DescribeInstanceHealth, aelb.DescribeTags, aelb.DescribeTargetGroups, aelb.DescribeTargetHealth, aelb.DescribeListeners,
                            ainspector.Action('Describe*'), ainspector.Action('List*'),
                            akinesis.Action('Get*'), akinesis.DescribeStream, akinesis.ListStreams,
                            akms.Decrypt,
                            asts.AssumeRole],
                    Resource=["*"])]))


@target.command()
@click.option('-r', '--region', 'region_list', multiple=True, prompt='Child Account Region List' if os.getenv('CLI_PROMPT') else None, help="list of accounts that are to be allowed tgit so publish logs into 'this' account (where the template is installed)")
@click.option('-a', '--account', 'account_list', multiple=True, prompt='Child Account ID List' if os.getenv('CLI_PROMPT') else None, help="list of regions that are being used to deploy into - affects policies created to allow cross-account communciation")
@click.option('--file', '-f', 'file_location', type=click.Path(), prompt="Save file path" if os.getenv('CLI_PROMPT') else None, help="Specific path to save the generated template in. If not specifies, defaults to package data directory.")
@click.option('--output-keys', 'output_keys', is_flag=True, prompt='Output Keys' if os.getenv('CLI_PROMPT') else None, help="boolean indicates whether template should include AWS IAM User access and secret key in the outputs of the template.")
@click.option('--dry-run', 'dry_run', is_flag=True, prompt='Dry Run' if os.getenv('CLI_PROMPT') else None, help="boolean indicates whether template should be printed to screen vs. being saved to file")
def generate(account_list=None, region_list=None, file_location=None, output_keys=False, dry_run=False):
    """CloudFormation template generator for use in creating the resources required to capture logs in a centrally managed account per UCSD standards."""
    if type(account_list) == tuple:
        account_list = list(account_list)

    parameter_groups = []

    region_list = region_list if region_list else ['us-west-1', 'us-west-2', 'us-east-1', 'us-east-2']
    t = Template()
    t.add_version("2010-09-09")
    t.add_description("UCSD Log Target AWS CloudFormation Template - this CFn template configures a given account to receive logs from other accounts so as to aggregate and then optionally forward those logs on to the UCSD Splunk installation.")

    # Create Kinesis and IAM Roles
    log_stream_shard_count = t.add_parameter(Parameter("LogStreamShardCount",
                                             Description="Number of shards to create within the AWS Kinesis stream created to handle CloudWatch Logs.",
                                             Type="Number",
                                             MinValue=1,
                                             MaxValue=64,
                                             Default=1))

    log_stream_retention_period = t.add_parameter(Parameter("LogStreamRetentionPeriod",
                                                  Description = "Number of hours to retain logs in the Kinesis stream.",
                                                  Type="Number",
                                                  MinValue=24,
                                                  MaxValue=120,
                                                  Default=24))

    parameter_groups.append({'Label': {'default': 'Log Stream Inputs'},
                         'Parameters': [log_stream_shard_count.name, log_stream_retention_period.name]})


    log_stream = t.add_resource(k.Stream("LogStream",
                                RetentionPeriodHours=Ref(log_stream_retention_period),
                                ShardCount=Ref(log_stream_shard_count)))

    firehose_bucket = t.add_resource(s3.Bucket('LogS3DeliveryBucket'))

    firehose_delivery_role = t.add_resource(iam.Role('LogS3DeliveryRole',
                                            AssumeRolePolicyDocument=Policy(
                                                Statement=[Statement(
                                                Effect=Allow,
                                                Action=[AssumeRole],
                                                Principal=Principal('Service', 'firehose.amazonaws.com'),
                                                Condition=Condition(StringEquals('sts:ExternalId', AccountId)))])))

    log_s3_delivery_policy = t.add_resource(iam.PolicyType('LogS3DeliveryPolicy',
                                           Roles=[Ref(firehose_delivery_role)],
                                           PolicyName='LogS3DeliveryPolicy',
                                           PolicyDocument=Policy(
                                               Statement=[Statement(
                                                   Effect=Allow,
                                                   Action=[as3.AbortMultipartUpload,
                                                           as3.GetBucketLocation,
                                                           as3.GetObject,
                                                           as3.ListBucket,
                                                           as3.ListBucketMultipartUploads,
                                                           as3.PutObject],
                                                   Resource=[
                                                        Join('', ['arn:aws:s3:::', Ref(firehose_bucket)]),
                                                        Join('', ['arn:aws:s3:::', Ref(firehose_bucket), '*'])]),
                                                Statement(
                                                    Effect=Allow,
                                                    Action=[akinesis.Action('Get*'), akinesis.DescribeStream, akinesis.ListStreams],
                                                    Resource=[
                                                        GetAtt(log_stream, 'Arn')
                                                    ])])))

    s3_firehose = t.add_resource(fh.DeliveryStream('LogToS3DeliveryStream',
                                 DependsOn=[log_s3_delivery_policy.name],
                                 DeliveryStreamName='LogToS3DeliveryStream',
                                 DeliveryStreamType='KinesisStreamAsSource',
                                 KinesisStreamSourceConfiguration=fh.KinesisStreamSourceConfiguration(
                                    KinesisStreamARN=GetAtt(log_stream, 'Arn'),
                                    RoleARN=GetAtt(firehose_delivery_role, 'Arn')
                                 ),
                                 S3DestinationConfiguration=fh.S3DestinationConfiguration(
                                    BucketARN=GetAtt(firehose_bucket, 'Arn'),
                                    BufferingHints=fh.BufferingHints(
                                        IntervalInSeconds=300,
                                        SizeInMBs=50
                                    ) ,
                                    CompressionFormat='UNCOMPRESSED',
                                    Prefix='firehose/' ,
                                    RoleARN=GetAtt(firehose_delivery_role, 'Arn'),
                                 )))

    t.add_output(Output('SplunkKinesisLogStream',
                 Value=GetAtt(log_stream, 'Arn'),
                 Description='ARN of the kinesis stream for log aggregation.'))


    # Generate Bucket with Lifecycle Policies

    ct_s3_key_prefix = t.add_parameter(Parameter('CloudTrailKeyPrefix',
                                       Type='String',
                                       Default='',
                                       Description='Key name prefix for logs being sent to S3'))

    bucket_name = t.add_parameter(Parameter("BucketName",
                                  Description="Name to assign to the central logging retention bucket",
                                  Type="String",
                                  AllowedPattern="([a-z]|[0-9])+",
                                  MinLength=2,
                                  MaxLength=64))

    glacier_migration_days = t.add_parameter(Parameter("LogMoveToGlacierInDays",
                                             Description="Number of days until logs are expired from S3 and transitioned to Glacier",
                                             Type="Number",
                                             Default=365))

    glacier_deletion_days = t.add_parameter(Parameter("LogDeleteFromGlacierInDays",
                                            Description="Number of days until logs are expired from Glacier and deleted",
                                            Type="Number",
                                            Default=365*7))

    parameter_groups.append({'Label': {'default': 'S3 Log Destination Parameters'},
                             'Parameters': [bucket_name.name, ct_s3_key_prefix.name, glacier_migration_days.name, glacier_deletion_days.name]})

    dead_letter_queue = t.add_resource(sqs.Queue('deadLetterQueue'))

    queue = t.add_resource(sqs.Queue('s3DeliveryQueue',
                           MessageRetentionPeriod=14*24*60*60, # 14 d * 24 h * 60 m * 60 s
                           VisibilityTimeout=5*60,
                           RedrivePolicy=sqs.RedrivePolicy(
                               deadLetterTargetArn=GetAtt(dead_letter_queue, 'Arn'),
                               maxReceiveCount=10
                           ))) # 5 m * 60 s per Splunk docs here: http://docs.splunk.com/Documentation/AddOns/released/AWS/ConfigureAWS#Configure_SQS

    t.add_output(Output('SplunkS3Queue',
                 Value=GetAtt(queue, 'Arn'),
                 Description='Queue for Splunk SQS S3 ingest'))

    t.add_output(Output('SplunkS3DeadLetterQueue',
                Value=GetAtt(dead_letter_queue, 'Arn'),
                Description="Dead letter queue for Splunk SQS S3 ingest"))


    t.add_resource(sqs.QueuePolicy('s3DeliveryQueuePolicy',
                   PolicyDocument=Policy(
                   Statement=[Statement(
                       Effect=Allow,
                       Principal=Principal("AWS", "*"),
                       Action=[asqs.SendMessage],
                       Resource=[GetAtt(queue, 'Arn')],
                       Condition=Condition(ArnLike("aws:SourceArn", Join('', ["arn:aws:s3:*:*:", Ref(bucket_name)]))))]),
                   Queues=[Ref(queue)]))

    bucket = t.add_resource(s3.Bucket("LogDeliveryBucket",
                            DependsOn=[log_stream.name, queue.name],
                            BucketName=Ref(bucket_name),
                            AccessControl="LogDeliveryWrite",
                            NotificationConfiguration=s3.NotificationConfiguration(
                                QueueConfigurations=[s3.QueueConfigurations(
                                    Event="s3:ObjectCreated:*",
                                    Queue=GetAtt(queue, 'Arn'))]),
                            LifecycleConfiguration=s3.LifecycleConfiguration(Rules=[
                                s3.LifecycleRule(
                                    Id="S3ToGlacierTransition",
                                    Status="Enabled",
                                    ExpirationInDays=Ref(glacier_deletion_days),
                                    Transition=s3.LifecycleRuleTransition(
                                        StorageClass="Glacier",
                                        TransitionInDays=Ref(glacier_migration_days)))])))

    bucket_policy = t.add_resource(s3.BucketPolicy("LogDeliveryBucketPolicy",
                                    Bucket=Ref(bucket),
                                    PolicyDocument=Policy(
                                        Statement=[
                                            Statement(
                                                Effect="Allow",
                                                Principal=Principal("Service", "cloudtrail.amazonaws.com"),
                                                Action=[GetBucketAcl],
                                                Resource=[GetAtt(bucket, 'Arn')]),
                                            Statement(
                                                Effect="Allow",
                                                Principal=Principal("Service", "cloudtrail.amazonaws.com"),
                                                Action=[PutObject],
                                                Condition=Condition(StringEquals({"s3:x-amz-acl": "bucket-owner-full-control"})),
                                                Resource=[Join('', [GetAtt(bucket, "Arn"), Ref(ct_s3_key_prefix), "/AWSLogs/", acct_id, "/*"]) for acct_id in account_list])])))

    splunk_sqs_s3_user = t.add_resource(iam.User('splunkS3SQSUser',
                                        Path='/',
                                        UserName='splunkS3SQSUser'))

    splunk_user_policy = t.add_resource(_generate_splunk_policy(users=[Ref(splunk_sqs_s3_user)]))

    t.add_output(Output('BucketName',
                 Description="Name of the bucket for CloudTrail log delivery",
                 Value=Ref(bucket)))

    # Log destination setup

    cwl_to_kinesis_role = t.add_resource(iam.Role('CWLtoKinesisRole',
                                         AssumeRolePolicyDocument=Policy(
                                            Statement=[Statement(
                                                Effect=Allow,
                                                Action=[AssumeRole],
                                                Principal=Principal("Service", Join('', ["logs.", Region, ".amazonaws.com"])))])))

    cwl_to_kinesis_policy_link = t.add_resource(iam.PolicyType('CWLtoKinesisPolicy',
                                               PolicyName='CWLtoKinesisPolicy',
                                               Roles=[Ref(cwl_to_kinesis_role)],
                                               PolicyDocument=Policy(
                                                 Statement=[
                                                     Statement(
                                                         Effect=Allow,
                                                         Resource=[GetAtt(log_stream, 'Arn')],
                                                         Action=[akinesis.PutRecord]),
                                                     Statement(
                                                         Effect=Allow,
                                                         Resource=[GetAtt(cwl_to_kinesis_role, 'Arn')],
                                                         Action=[IAMPassRole])])))

    log_destination = t.add_resource(cwl.Destination('CWLtoKinesisDestination',
                                     DependsOn=[cwl_to_kinesis_policy_link.name],
                                     DestinationName='CWLtoKinesisDestination',
                                     DestinationPolicy=_generate_log_destination_policy_test('CWLtoKinesisDestination', account_list),
                                     RoleArn=GetAtt(cwl_to_kinesis_role, 'Arn'),
                                     TargetArn=GetAtt(log_stream, 'Arn')))

    t.add_output(Output('childAccountLogDeliveryDestinationArn',
                 Value=GetAtt(log_destination,'Arn'),
                 Description='Log Destination to specify when deploying the source cloudformation template in other accounts.'))

    if output_keys:
        splunk_user_creds = t.add_resource(iam.AccessKey('splunkAccountUserCreds',
                                           UserName=Ref(splunk_sqs_s3_user)))

        t.add_output(Output('splunkUserAccessKey',
                     Description='AWS Access Key for the user created for splunk to use when accessing logs',
                     Value=Ref(splunk_user_creds)))

        t.add_output(Output('splunkUserSecretKey',
                     Description='AWS Secret Access Key ID for the user created for splunk to use when accessing logs',
                     Value=GetAtt(splunk_user_creds, 'SecretAccessKey')))


    t.add_output(Output('splunkCWLRegion',
                 Description="The AWS region that contains the data. In aws_cloudwatch_logs_tasks.conf, enter the region ID.",
                 Value=Region))

    t.add_output(Output("DeploymentAccount",
                 Value=AccountId,
                 Description="Convenience Output for referencing AccountID of the log aggregation account"))

    t.add_metadata({"AWS::CloudFormation::Interface": {"ParameterGroups": parameter_groups}})

    if dry_run:
        print(t.to_json())
    else:
        save_path = file_location if file_location else os.path.join(log_aggregation_cf, 'log_targets.json')
        with open (save_path, 'w') as f:
            f.write(t.to_json())


def _generate_log_destination_policy_test(log_destination_name, account_list=[]):
    """Helper method to generate the log destination policy. Per Account in `account_list` build a policy document tha allows the account list for the given region to write to the log destination.
    This is complicated by the issue that CloudFormation takes this as a string vs. as a Policy/JSON document, so here we are, building a string from a JSON doc in pieces. Given that it's not a JSON doc directly in the template, all this work is to ensure that the AWS AccountID isn't needed as a static string input thus making this portable vs. needing to be hard coded per account."""
    policy_doc = []

    policy_doc.append('{"Version" : "2012-10-17","Statement" : [{"Sid" : "","Effect" : "Allow","Principal" : {"AWS" : [' + ','.join(['"%s"' % s for s in account_list]) + ']},')
    policy_doc.append('"Action" : "logs:PutSubscriptionFilter","Resource" : "arn:aws:logs:')
    policy_doc.append(Join(':', [Region, AccountId, "destination", log_destination_name]))
    policy_doc.append('"}]}')
    return Join("", policy_doc)



def _generate_log_destination_policy(log_destination_name, account_list=[]):
    """Helper method to generate the log destination policy. Per Account in `account_list` build a policy document tha allows the account list for the given region to write to the log destination.
    This is complicated by the issue that CloudFormation takes this as a string vs. as a Policy/JSON document, so here we are, building a string from a JSON doc in pieces. Given that it's not a JSON doc directly in the template, all this work is to ensure that the AWS AccountID isn't needed as a static string input thus making this portable vs. needing to be hard coded per account."""
    policy_doc = []

    policy_doc.append('{"Version" : "2012-10-17","Statement" : [')

    for s in account_list:
        policy_doc.append('{"Sid" : "","Effect" : "Allow","Principal" : {"AWS" : "%s"},"Action" : "logs:PutSubscriptionFilter", "Resource" : "arn:aws:logs:' % s)
        policy_doc.append(Join(':', [Region, AccountId, "destination", log_destination_name]))
        policy_doc.append('"}')
        policy_doc.append(',')

    if policy_doc[-1] == ',':
        policy_doc = policy_doc[:-1]

    policy_doc.append(']}')
    return Join("", policy_doc)
