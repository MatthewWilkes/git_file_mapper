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

progress_indicator: contextvars.ContextVar[
    t.Callable[[int], t.Any]
] = contextvars.ContextVar("progress_indicator")


class Transformer(t.Protocol):
    def __call__(self, filename: str, contents: bytes) -> bytes:
        ...


class ReferenceNamer(t.Protocol):
    def __call__(self, reference_name: str) -> str:
        ...


def null_transformer(filename: str, contents: bytes) -> bytes:
    return contents


def transform_blob(blob: git.Blob, transformer: Transformer) -> git.Blob:
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


def transform_tree(tree: git.Tree, transformer: Transformer) -> git.Tree:
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
            contents.append((new_tree.binsha, stat.S_IFDIR, subtree.name))

        with BytesIO() as new_tree_stream:
            tree_to_stream(contents, new_tree_stream.write)
            length = new_tree_stream.tell()
            new_tree_stream.seek(0)
            new_tree_obj = tree.repo.odb.store(
                IStream(git.Tree.type, length, new_tree_stream)
            )
        hashes[tree.binsha] = new_tree_obj.binsha
    else:
        binsha = hashes[tree.binsha]
        new_tree_obj = tree.repo.odb.info(binsha)

    new_tree = tree.repo.tree(new_tree_obj.hexsha.decode("ascii"))
    return new_tree


def transform_commit(commit: git.Commit, transformer: Transformer) -> git.Commit:
    hashes = hash_mapping.get()
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
    hashes[commit.binsha] = new_commit.binsha
    return new_commit


def map_commits(
    repo: git.Repo,
    transformer: Transformer,
    reference_name_generator: t.Optional[ReferenceNamer] = None,
) -> t.Dict[git.Commit, git.Commit]:
    token = hash_mapping.set({})
    commit_mapping = {}
    progress: t.Optional[t.Callable[[int], t.Any]]
    try:
        progress = progress_indicator.get()
    except LookupError:
        progress = None

    try:
        for branch in repo.branches + repo.tags:
            for commit in repo.iter_commits(branch):
                new_commit = transform_commit(commit, transformer)
                commit_mapping[commit] = new_commit
                if progress:
                    progress(1)
            if reference_name_generator:
                new_name = reference_name_generator(branch.name)
                new_head = commit_mapping[branch.commit]
                if isinstance(branch, git.refs.Head):
                    repo.create_head(new_name, commit=new_head)
                elif isinstance(branch, git.refs.TagReference):
                    repo.create_tag(new_name, ref=new_head)
    finally:
        hash_mapping.reset(token)
    return commit_mapping
