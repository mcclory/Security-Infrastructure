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

from awacs.aws import Allow, Statement, Principal, Policy, Condition, StringEquals
from awacs.kinesis import PutRecord as KinesisPutRecord
from awacs.iam import PassRole as IAMPassRole
from awacs.sts import AssumeRole
from awacs.s3 import GetBucketAcl, PutObject

log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.group()
def cli():
    pass


@cli.group()
def target():
    """Command group pertaining to the management of CloudFormation templates designed to configure the AWS account where infrastructure-level logging is aggregated to."""
    pass

@target.command()
@click.option('--account_id', '-a', 'account_id_list', multiple=True)
@click.option('--bucket-name', '-b', 'bucket_name', envvar='BUCKETNAME')
@click.option('--log-file-prefix', 'log_file_prefix', '-p')
@click.option('--profile', '-p', 'aws_profile', envvar='AWS_PROFILE')
@click.option('--region', '-r', 'aws_region', envvar='AWS_REGION')
@click.option('--dry-run', 'dry_run', is_flag=True, prompt='Dry Run' if os.getenv('CLI_PROMPT') else None, help="boolean indicates whether template should be printed to screen vs. being saved to file")
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


    if dry_run:
        print(cloudformation_template)
    else:
        # perform calls to AWS and return results to stdout
        pass


@target.command()
@click.option('-r', '--region', 'region_list', multiple=True, prompt='Child Account Region List' if os.getenv('CLI_PROMPT') else None, help="list of accounts that are to be allowed tgit so publish logs into 'this' account (where the template is installed)")
@click.option('-a', '--account', 'account_list', multiple=True, prompt='Child Account ID List' if os.getenv('CLI_PROMPT') else None, help="list of regions that are being used to deploy into - affects policies created to allow cross-account communciation")
@click.option('--file', '-f', 'file_location', type=click.Path(), prompt="Save file path" if os.getenv('CLI_PROMPT') else None, help="Specific path to save the generated template in. If not specifies, defaults to package data directory.")
@click.option('--dry-run', 'dry_run', is_flag=True, prompt='Dry Run' if os.getenv('CLI_PROMPT') else None, help="boolean indicates whether template should be printed to screen vs. being saved to file")
def generate(account_list=None, region_list=None, file_location=None, dry_run=False):
    """CloudFormation template generator for use in creating the resources required to capture logs in a centrally managed account per UCSD standards."""
    if type(account_list) == tuple:
        account_list = list(account_list)

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

    log_stream = t.add_resource(k.Stream("LogStream",
        RetentionPeriodHours=Ref(log_stream_retention_period),
        ShardCount=Ref(log_stream_shard_count)))

    log_ingest_iam_role = t.add_resource(iam.Role('LogIngestIAMRole',
        AssumeRolePolicyDocument=Policy(
            Statement=[Statement( Effect=Allow, Action=[AssumeRole], Principal=Principal("Service", Join(".", ["logs", Region, "amazonaws.com"]))) for region_name in region_list])))

    log_ingest_iam_policy = t.add_resource(iam.PolicyType("LogIngestIAMPolicy",
        PolicyName="logingestpolicy20180211",
        Roles=[Ref(log_ingest_iam_role)],
        PolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[KinesisPutRecord],
                    Resource=[GetAtt(log_stream, "Arn")]),
                Statement(
                    Effect=Allow,
                    Action=[IAMPassRole],
                    Resource=[GetAtt(log_ingest_iam_role, "Arn")])])))

    t.add_output(Output('LogDeliveryIAMRole',
                 Description="ARN of the IAM role to supply to the source_log template for log delivery to the Kinesis Stream",
                 Value=GetAtt(log_ingest_iam_role, "Arn")))

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

    bucket = t.add_resource(s3.Bucket("LogDeliveryBucket",
                            DependsOn=[log_stream.name],
                            BucketName=Ref(bucket_name),
                            AccessControl="LogDeliveryWrite",
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

    t.add_output(Output('BucketName',
                 Description="Name of the bucket for CloudTrail log delivery",
                 Value=Ref(bucket)))

    # Log destination setup
    log_destination_name = "LogIngestDestination"
    log_destination = t.add_resource(cwl.Destination(log_destination_name,
                                     DestinationName=log_destination_name,
                                     DestinationPolicy=_generate_log_destination_policy(log_destination_name, account_list),
                                     TargetArn=GetAtt(log_stream, "Arn"),
                                     RoleArn=GetAtt(log_ingest_iam_role, "Arn"),
                                     DependsOn=[log_ingest_iam_policy.name, bucket.name]))

    t.add_output(Output("LogDeliveryDestinationArn",
                 Value=GetAtt(log_destination, "Arn"),
                 Description="ARN of the Log Destination for log aggregation via CloudWatch Logs"))

    t.add_output(Output("DeploymentAccount",
                 Value=AccountId,
                 Description="Convenience Output for referencing AccountID of the log aggregation account"))

    if dry_run:
        print(t.to_json())
    else:
        save_path = file_location if file_location else os.path.join(log_aggregation_cf, 'log_targets.json')
        with open (save_path, 'w') as f:
            f.write(t.to_json())



def _generate_log_destination_policy(log_destination_name, account_list=[]):
    """Helper method to generate the log destination policy. Per Account in `account_list` build a policy document tha allows the account list for the given region to write to the log destination.
    This is complicated by the issue that CloudFormation takes this as a string vs. as a Policy/JSON document, so here we are, building a string from a JSON doc in pieces. Given that it's not a JSON doc directly in the template, all this work is to ensure that the AWS AccountID isn't needed as a static string input thus making this portable vs. needing to be hard coded per account."""
    policy_doc = []

    policy_doc.append('{"Version" : "2012-10-17","Statement" : [')
    policy_doc.append('{"Sid" : "",')
    policy_doc.append('"Effect" : "Allow",')
    policy_doc.append('"Principal" : {"AWS" : [' + ','.join(['"%s"' % s for s in account_list]) + ']},')
    policy_doc.append('"Action" : "logs:PutSubscriptionFilter",')
    policy_doc.append('"Resource" : "arn:aws:logs:')
    policy_doc.append(Join(':', [Region, AccountId, "destination", log_destination_name]))
    policy_doc.append('"}')
    policy_doc.append(']}')
    return Join("", policy_doc)
