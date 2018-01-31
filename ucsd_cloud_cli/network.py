import click

@click.group()
def network():
    pass

@network.command()
def list(profile_name, region):
    pass
