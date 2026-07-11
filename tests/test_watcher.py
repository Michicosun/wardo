from wardo.services import watcher


def test_is_pr_watched_prefix(node):
    pr = node(files=["src/a.py", "docs/b.md", "src/deep/c.py"])
    assert watcher.is_pr_watched(pr, ["src/", "lib/"])
    assert watcher.is_pr_watched(pr, ["docs/"])
    assert not watcher.is_pr_watched(pr, ["lib/"])


def test_is_pr_watched_substring(node):
    pr = node(files=["src/Processors/QueryPlan/Optimizations/foo.cpp"])
    assert watcher.is_pr_watched(pr, ["QueryPlan"])
    assert not watcher.is_pr_watched(pr, ["MergeTree"])


def test_is_pr_watched_regex(node):
    pr = node(files=["src/Storages/MergeTree/MergeTreeData.cpp"])
    assert watcher.is_pr_watched(pr, [r"MergeTree.*\.cpp$"])
    assert watcher.is_pr_watched(pr, [r"^src/(Storages|Processors)/"])
    assert not watcher.is_pr_watched(pr, [r"\.py$"])
