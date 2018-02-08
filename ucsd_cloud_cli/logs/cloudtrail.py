import click

@click.group()
def cloudtrail():
    pass


@cloudtrail.command()
def configure():
    pass


@cloudtrail.command()
def remove():
    pass
