import click

@click.group()
def vpc():
    pass


@vpc.command()
def configure():
    pass


@vpc.command()
def remove():
    pass
