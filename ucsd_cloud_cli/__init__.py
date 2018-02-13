from .logs import logs
from .sec import sec
import click
import os

data_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
cf_data_dir = os.path.join(data_dir, 'cloudformation')

cli = click.CommandCollection(sources=[logs])

VERSION = '0.1.0'
