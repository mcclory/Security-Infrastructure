import click

@click.group()
def cloudwatch():
    pass

@cloudwatch.command()
def configure():
    pass


@cloudwatch.command()
def remove():
    pass
