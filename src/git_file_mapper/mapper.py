import typing as t

import git


TRANSFORMER = t.Callable[[str, bytes], bytes]


def null_transformer(filename: str, contents: bytes) -> bytes:
    return contents


def transform_blob(blob: git.Blob, transformer: TRANSFORMER) -> git.Blob:
    return blob


def transform_tree(tree: git.Tree, transformer: TRANSFORMER) -> git.Tree:
    return tree


def transform_commit(commit: git.commit, transformer: TRANSFORMER) -> git.Commit:
    return commit


def map_commits(repo: git.Repo, transformer: TRANSFORMER):
    for commit in repo.iter_commits():
        new_commit = transform_commit(commit, transformer)
