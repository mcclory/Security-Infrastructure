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
def service():
    pass


@service.command('add')
@click.option('--service-name', 's', 'service_name')
def service_add(service_name):
    if service_name.lower() not in SUPPORTED_SERVICES:
        raise NotImplementedError('Service %s is not implemented in this CLI' % service_name)
    pass


@service.command('remove')
def service_remove(service_name):
    if service_name.lower() not in SUPPORTED_SERVICES:
        raise NotImplementedError('Service %s is not implemented in this CLI' % service_name)
    pass
