import click
from .. import cf_data_dir
import json
import os

from troposphere import GetAtt, Ref, Join, Template, AccountId, Region, Output, Parameter
import troposphere.iam as iam
import troposphere.s3 as s3
import troposphere.cloudtrail as ct
import troposphere.logs as cwl
import troposphere.kinesis as k

from awacs.aws import Allow, Statement, Principal, Policy
from awacs.kinesis import PutRecord as KinesisPutRecord
from awacs.iam import PassRole as IAMPassRole
from awacs.sts import AssumeRole

log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.group()
def cli():
    pass


@cli.group()
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


@target.command()
@click.option('--dry-run', 'dry_run', is_flag=True)
@click.option('--deploy-account-id', '-d', 'deploy_account_id')
@click.option('--deploy-region-name', '-n', 'deploy_region_name')
@click.option('-r', '--region', 'region_list', multiple=True)
@click.option('-a', '--account', 'account_list', multiple=True)
def generate(deploy_account_id='123456789012', deploy_region_name='us-west-2', account_list=None, region_list=None, dry_run=False):
    if type(account_list) == tuple:
        account_list = list(account_list)

    region_list = region_list if region_list else ['us-west-1', 'us-west-2', 'us-east-1', 'us-east-2']
    t = Template()

    # Generate Bucket with Lifecycle Policies
    bucket_name = t.add_parameter(Parameter("BucketName",
        Description="Name to assign to the central logging retention bucket",
        Type="String",
        AllowedPattern="([a-z]|[0-9])+",
        MinLength=2,
        MaxLength=64))

    s3_expiration_in_days = t.add_parameter(Parameter("LogS3ExpirationInDays",
        Description="Number of days until logs are expired from S3 and transitioned to Glacier",
        Type="Number",
        Default=365))

    glacier_expiration_in_days = t.add_parameter(Parameter("GlacierExpirationInDays",
        Description="Number of days until logs are expired from Glacier and deleted",
        Type="Number",
        Default=365*7))

    bucket = t.add_resource(s3.Bucket("LogDeliveryBucket",
        BucketName=Ref(bucket_name),
        AccessControl="LogDeliveryWrite",
        LifecycleConfiguration=s3.LifecycleConfiguration(Rules=[
            s3.LifecycleRule(
                Id="S3ToGlacierTransition",
                Status="Enabled",
                ExpirationInDays=Ref(s3_expiration_in_days),
                Transition=s3.LifecycleRuleTransition(
                    StorageClass="Glacier",
                    TransitionInDays=Ref(glacier_expiration_in_days)))])))

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
        MinValue=1,
        MaxValue=24,
        Default=4))

    log_stream = t.add_resource(k.Stream("LogStream",
        RetentionPeriodHours=Ref(log_stream_shard_count),
        ShardCount=Ref(log_stream_retention_period)))

    log_ingest_iam_role = t.add_resource(iam.Role('LogIngestIAMRole',
        AssumeRolePolicyDocument=Policy(
            Statement=[Statement( Effect=Allow, Action=[AssumeRole], Principal=Principal("Service", Join(".", ["logs", Region, "amazonaws.com"]))) for region_name in region_list])))

    log_ingest_iam_policy = t.add_resource(iam.PolicyType("LogIngestIAMPolicy",
        PolicyName=Join("LogIngestIAMPolicy-", Region),
        Roles=[GetAtt(log_ingest_iam_role, "Arn")],
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

    log_destination_name = "LogIngestDestination"
    log_destination = t.add_resource(cwl.Destination(log_destination_name,
        DestinationName="LogIngestDestination",
        DestinationPolicy=_generate_log_destination_policy(log_destination_name, deploy_region_name, deploy_account_id, account_list),
        TargetArn=GetAtt(log_stream, "Arn"),
        RoleArn=GetAtt(log_ingest_iam_role, "Arn")))

    if dry_run:
        print(t.to_json())
    else:
        template_name = 'log_targets.json'
        with open (os.path.join(log_aggregation_cf, template_name), 'w') as f:
            f.write(t.to_json())

    t.add_output(Output("StreamArn",
                 Value=GetAtt(log_stream, "Arn"),
                 Description="ARN of the Kinesis stream for log aggregation via CloudWatch Logs"))

    t.add_output(Output("DeploymentAccount",
                 Value=AccountId,
                 Description="Convenience Output for referencing AccountID of the log aggregation account"))


def _generate_log_destination_policy(log_destination_name, region, account_id, account_list=[]):
    statements = []
    for account_no in account_list:
        statements.append({"Effect":"Allow", "Principal":{"AWS": account_no}, "Action": "logs.PutSubscriptionFilter", "Resource": "arn:aws:logs:%s:%s:destination:%s" % (region, account_id, log_destination_name)})
    return json.dumps({"Version": "2012-10-17", "Statement": statements})
