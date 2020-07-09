import os
import shlex

import click
import git

from .mapper import (
    map_commits,
    get_glob_transformer,
    subprocess_transformer,
    progress_indicator,
    ReferenceNamer,
)


def suffixer(suffix: str) -> ReferenceNamer:
    def add_suffix(reference_name: str) -> str:
        return reference_name + "-" + suffix

    return add_suffix


@click.argument("suffix")
@click.option("--transform", type=(str, str), multiple=True)
@click.command()
def mapper(suffix, transform) -> None:
    transformers = {}
    for glob, programme in transform:
        transformers[glob] = subprocess_transformer(shlex.split(programme))
    transformer = get_glob_transformer(transformers)

    if suffix:
        renamer = suffixer(suffix)

    repo = git.Repo(os.getcwd())
    num_commits = 0
    with click.progressbar(
        repo.branches + repo.tags, label="Resolving references"
    ) as bar:
        for ref in bar:
            num_commits += sum(1 for x in repo.iter_commits(ref))

    with click.progressbar(label="Commits", length=num_commits) as progressbar:
        click.secho(progressbar.format_progress_line(), nl=False)  # type: ignore
        token = progress_indicator.set(progressbar.update)
        try:
            map_commits(repo, transformer, renamer)
        finally:
            progress_indicator.reset(token)
