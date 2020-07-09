import os

import click
import git

from .mapper import map_commits, null_transformer, progress_indicator


@click.command()
def mapper() -> None:
    repo = git.Repo(os.getcwd())
    num_commits = 0
    for ref in repo.branches + repo.tags:
        num_commits += sum(1 for x in repo.iter_commits(ref))

    with click.progressbar(label="Commits", length=num_commits) as progressbar:
        token = progress_indicator.set(progressbar.update)
        try:
            map_commits(repo, null_transformer)
        finally:
            progress_indicator.reset(token)
    click.secho("Complete", fg="green")
