import contextvars
from io import BytesIO
import stat
import typing as t

import git
from git.objects.util import altz_to_utctz_str
from git.objects.fun import tree_to_stream
from gitdb.base import IStream


hash_mapping: contextvars.ContextVar[t.Dict[bytes, bytes]] = contextvars.ContextVar(
    "hash_mapping"
)
TRANSFORMER = t.Callable[[str, bytes], bytes]


def null_transformer(filename: str, contents: bytes) -> bytes:
    return contents


def transform_blob(blob: git.Blob, transformer: TRANSFORMER) -> git.Blob:
    hashes = hash_mapping.get()
    if blob.binsha not in hashes:
        new_contents = transformer(blob.path, blob.data_stream.read())
        with BytesIO(new_contents) as stream:
            new_blob = blob.repo.odb.store(
                IStream(git.Blob.type, len(new_contents), stream)
            )
        hashes[blob.binsha] = new_blob.binsha
    else:
        binsha = hashes[blob.binsha]
        new_blob = blob.repo.odb.info(binsha)
    return new_blob


def transform_tree(tree: git.Tree, transformer: TRANSFORMER) -> git.Tree:
    hashes = hash_mapping.get()
    contents = []

    if tree.binsha not in hashes:
        for blob in tree.blobs:
            new_blob = transform_blob(blob, transformer)
            contents.append((new_blob.binsha, blob.mode, blob.name))

        for subtree in tree.trees:
            if subtree.binsha not in hashes:
                new_tree = transform_tree(subtree, transformer)
            else:
                new_tree = subtree
            hashes[subtree.binsha] = new_tree.binsha
            contents.append((new_tree.binsha, stat.S_IFDIR, subtree.name))

        with BytesIO() as new_tree_stream:
            tree_to_stream(contents, new_tree_stream.write)
            length = new_tree_stream.tell()
            new_tree_stream.seek(0)
            new_tree_obj = tree.repo.odb.store(
                IStream(git.Tree.type, length, new_tree_stream)
            )
    else:
        binsha = hashes[tree.binsha]
        new_tree_obj = blob.repo.odb.info(binsha)

    new_tree = tree.repo.tree(new_tree_obj.hexsha.decode("ascii"))
    return new_tree


def transform_commit(commit: git.Commit, transformer: TRANSFORMER) -> git.Commit:
    new_tree = transform_tree(commit.tree, transformer)
    author_datetime = "{} {}".format(
        commit.authored_date, altz_to_utctz_str(commit.author_tz_offset)
    )
    committer_datetime = "{} {}".format(
        commit.committed_date, altz_to_utctz_str(commit.committer_tz_offset)
    )

    new_parents = [transform_commit(parent, transformer) for parent in commit.parents]
    new_commit = git.Commit.create_from_tree(
        commit.repo,
        new_tree,
        commit.message,
        new_parents,
        author=commit.author,
        committer=commit.committer,
        author_date=author_datetime,
        commit_date=committer_datetime,
    )
    return new_commit


def map_commits(
    repo: git.Repo, transformer: TRANSFORMER
) -> t.Dict[git.Commit, git.Commit]:
    hash_mapping.set({})
    commit_mapping = {}
    for commit in repo.iter_commits():
        new_commit = transform_commit(commit, transformer)
        commit_mapping[commit] = new_commit
        print(f"{commit} becomes {new_commit}")
    return commit_mapping
