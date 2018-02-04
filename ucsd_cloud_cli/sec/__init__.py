import click
from .isolate import isolate
from .snapshot import snapshot
from .. import cf_data_dir, data_dir

sec = click.CommandCollection(sources=[isolate, snapshot])
