# Git File Mapper 

A programme that applies a map operation to files in git. This can be used to transform an entire tree of reachable objects in a git repository. This does not remove the existing objects, it creates new ones.

While this can be used to apply an automatic formatter (such as Python's black) to the entire history of a project, meaning that every file in every revision is compliant. However, this is *not* a good way to apply a formatter. Like all operations that change the history of a git repository, this can cause trouble as any users who have an old copy of the tree will need to update their checkouts to use the new references. This can be an absolute nightmare for branching.

The reason I created this is to allow the creation of read-only parallel trees that have an automatic transform applied. Specifically, I plan to use this to create a history of `apd.sensors` that does not include the type hints, so people who aren't interested in typing can browse the code for Advanced Python Development more easily.

## Usage

For example, to apply black to all Python files and save references with a suffix, so `main` becomes `main-black`,
do:

    $ git-map-files black --transform "*.py" "black -"

You may pass any number of `--transform` arguments. They will be parsed in order, with the first matching transform being the only one that's applied. If no transforms match then no change is made.

This will create variants of all branches and tags, so you must ensure that there are no conflicts before running.
