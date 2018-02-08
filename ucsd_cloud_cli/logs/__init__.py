import click
from .target import target
from .. import cf_data_dir


logs = click.CommandCollection(sources=[target])
