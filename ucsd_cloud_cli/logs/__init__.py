import click
from .target import cli as target
from .source import cli as source
from .. import cf_data_dir


logs = click.CommandCollection(sources=[target, source])
