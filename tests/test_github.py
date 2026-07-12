from wardo.config import config
from wardo.clients import github


class FakeGH(github.GitHub):
    def __init__(self, nodes):
        super().__init__(config.GithubConfig(token="x"))
        self.nodes = nodes
        self.queries = []

    def _search_prs(self, q, page_size=100):
        self.queries.append(q)
        yield from self.nodes


def test_open_prs_filters_by_created_at(node):
    cutoff = github._parse_ts("2026-07-04T00:00:00Z")
    gh = FakeGH([
        node(number=2, created="2026-07-06T00:00:00Z"),
        node(number=4, created="2026-07-09T00:00:00Z"),
        node(number=1, created="2026-07-01T00:00:00Z"),
    ])
    result = list(gh.open_prs("x/y", cutoff))
    assert [pr.number for pr in result] == [2, 4]
    assert gh.queries == ["repo:x/y is:pr is:open created:>=2026-07-04T00:00:00+00:00 sort:created-desc"]


def test_merged_prs_filters_by_merged_at(node):
    cutoff = github._parse_ts("2026-07-04T00:00:00Z")
    gh = FakeGH([
        node(number=3, merged="2026-07-05T00:00:00Z"),
        node(number=5, merged="2026-07-10T00:00:00Z"),
        node(number=2, merged="2026-07-01T00:00:00Z"),
    ])
    result = list(gh.merged_prs("x/y", cutoff))
    assert [pr.number for pr in result] == [3, 5]
    assert gh.queries == ["repo:x/y is:pr is:merged merged:>=2026-07-04T00:00:00+00:00 sort:updated-desc"]


def test_parse_pr():
    raw = {
        "number": 7, "title": "T", "url": "https://github.com/x/y/pull/7",
        "createdAt": "2026-07-10T00:00:00Z", "updatedAt": "2026-07-10T01:00:00Z", "mergedAt": None,
        "author": None,
        "files": {"nodes": [{"path": "src/a.py"}]},
    }
    pr = github._parse_pr(raw)
    assert pr.number == 7
    assert pr.author == "ghost"
    assert pr.merged_at is None
    assert pr.files == ["src/a.py"]
