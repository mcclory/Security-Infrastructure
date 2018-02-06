import click
from .cloudtrail import cloudtrail
from .cloudwatch import cloudwatch
from .vpc import vpc
from .. import cf_data_dir

logs = click.CommandCollection(sources=[cloudtrail, cloudwatch, vpc])
