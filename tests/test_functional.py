import os
import tempfile

import git
import pytest

from git_file_mapper.mapper import (
    map_commits,
    transform_commit,
    transform_blob,
    hash_mapping,
)


def world_transformer(filename: str, contents: bytes) -> bytes:
    return contents.replace(b"world", b"planet")


@pytest.fixture
def root():
    with tempfile.TemporaryDirectory() as tempdir:
        yield tempdir


@pytest.fixture
def empty_git_repo(root):
    repo = git.Repo.init(root)
    return repo


@pytest.fixture
def transform_data():
    data = {}
    token = hash_mapping.set(data)
    try:
        yield data
    finally:
        hash_mapping.reset(token)


@pytest.fixture
def git_repo(root, empty_git_repo):
    repo = empty_git_repo

    filename = os.path.join(root, "one.py")
    with open(filename, "wt", encoding="utf-8") as pfile:
        pfile.write('print("hello world")\n')
    repo.index.add([filename])
    repo.index.commit("add hello world")

    with open(filename, "a", encoding="utf-8") as pfile:
        pfile.write('print("oh, brave new world")\n')
    repo.index.add([filename])
    repo.index.commit("add second message")

    return repo


def test_apply_mapper(git_repo):
    replaced = map_commits(git_repo, world_transformer)

    HEAD = git_repo.head.commit
    first = HEAD.parents[0]
    assert "hello world" in git_repo.git.show(first)
    assert "brave new world" in git_repo.git.show(HEAD)

    new_HEAD = replaced[HEAD]
    new_first = replaced[first]
    assert "hello planet" in git_repo.git.show(new_first)
    assert "brave new planet" in git_repo.git.show(new_HEAD)

    assert first.author == new_first.author
    assert first.authored_datetime == new_first.authored_datetime
    assert new_HEAD.parents == [new_first]


def test_convert_individual_commit(git_repo, transform_data):
    HEAD = git_repo.head.commit
    first = HEAD.parents[0]
    transform_commit(first, world_transformer)

    # We should have transformed the commit, the root tree and one file
    assert len(transform_data) == 3

    new_first_binsha = transform_data[first.binsha]
    new_first_hexsha = git_repo.odb.info(new_first_binsha).hexsha
    new_first = git_repo.commit(new_first_hexsha.decode("ascii"))

    assert '+print("hello planet")' in git_repo.git.show(new_first)


def test_convert_commit_includes_parents(git_repo, transform_data):
    HEAD = git_repo.head.commit
    transform_commit(HEAD, world_transformer)

    # We should have transformed the commit, the root tree and one file for 2 commits
    assert len(transform_data) == 6
