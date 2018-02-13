import click
from .isolate import isolate
from .snapshot import snapshot

sec = click.CommandCollection(sources=[isolate, snapshot])
