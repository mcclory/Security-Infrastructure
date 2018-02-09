import click
from .target import cli as target
from .accounts import cli as account
from .. import cf_data_dir


logs = click.CommandCollection(sources=[target, account])
