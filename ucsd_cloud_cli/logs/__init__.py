import click
from .target import cli as target
from .source import cli as source
import os

logs = click.CommandCollection(sources=[target, source])
