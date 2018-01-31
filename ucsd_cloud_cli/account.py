import click

@click.group()
def account():
    pass

@account.command()
def list():
    pass
