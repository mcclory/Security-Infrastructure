import click
from .. import cf_data_dir
import yaml
import os

log_aggregation_cf = os.path.join(cf_data_dir, 'log_aggregation')
SUPPORTED_SERVICES = ['cloudtrail', 'cloudwatch', 'vpc_flow_logs']

@click.group()
def cli():
    pass

@cli.group()
def account():
    pass

@account.command('add')
@click.option('--account-no', '-a', 'account_no')
def account_add(account_no):
    pass

@account.command('remove')
def account_remove(account_no):
    pass
