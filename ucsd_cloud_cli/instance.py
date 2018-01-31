import click

@click.group()
def instance():
    pass

@instance.command()
def list(profile_name, region):
    pass
