import os

import click
import git

from .mapper import map_commits, null_transformer


@click.command()
def mapper() -> None:
    repo = git.Repo(os.getcwd())
    map_commits(repo, null_transformer)
    pass
