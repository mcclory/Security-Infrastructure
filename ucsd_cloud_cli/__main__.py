import click
from .account import account
from .instance import instance
from .network import network
from .region import region
from .service import service

cli = click.CommandCollection(sources=[account, instance, network, region, service])

if __name__ == '__main__':
    cli()
