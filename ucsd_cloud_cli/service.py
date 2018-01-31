import click

@click.group()
def service():
    pass

@service.command()
def list():
    pass
