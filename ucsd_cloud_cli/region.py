import click

@click.group()
def region():
    pass

@region.command()
def list():
    pass
