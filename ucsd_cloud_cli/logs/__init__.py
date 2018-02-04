import click
from .cloudtrail import cloudtrail
from .cloudwatch import cloudwatch
from .vpc import vpc

logs = click.CommandCollection(sources=[cloudtrail, cloudwatch, vpc])
