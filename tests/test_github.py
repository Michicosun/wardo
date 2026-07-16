import pytest

from wardo.clients import github
from wardo.config import config


class FakeGH(github.GitHub):
    def __init__(self, nodes):
        super().__init__(config.GithubConfig(token="x"))
        self.nodes = nodes
        self.queries = []

    def _search_prs(self, q, page_size=100):
        self.queries.append(q)
        yield from self.nodes


CUTOFF = "2026-07-04T00:00:00Z"


@pytest.mark.parametrize("method, prs, expected, query", [
    ("open_prs",
     [dict(number=2, created="2026-07-06T00:00:00Z"),
      dict(number=4, created="2026-07-09T00:00:00Z"),
      dict(number=1, created="2026-07-01T00:00:00Z")],
     [2, 4],
     "repo:x/y is:pr is:open created:>=2026-07-04T00:00:00+00:00 sort:created-desc"),
    ("merged_prs",
     [dict(number=3, merged="2026-07-05T00:00:00Z"),
      dict(number=5, merged="2026-07-10T00:00:00Z"),
      dict(number=2, merged="2026-07-01T00:00:00Z")],
     [3, 5],
     "repo:x/y is:pr is:merged merged:>=2026-07-04T00:00:00+00:00 sort:updated-desc"),
    ("closed_prs",
     [dict(number=3, closed="2026-07-05T00:00:00Z"),
      dict(number=4, merged="2026-07-06T00:00:00Z"),
      dict(number=2, closed="2026-07-01T00:00:00Z")],
     [3],
     "repo:x/y is:pr is:closed is:unmerged closed:>=2026-07-04T00:00:00+00:00 sort:updated-desc"),
])
def test_queries_filter_by_cutoff(node, method, prs, expected, query):
    gh = FakeGH([node(**kwargs) for kwargs in prs])
    result = list(getattr(gh, method)("x/y", github._parse_ts(CUTOFF)))
    assert [pr.number for pr in result] == expected
    assert gh.queries == [query]


def test_date_field_overrides_search_qualifier():
    gh = FakeGH([])
    list(gh.merged_prs("x/y", github._parse_ts(CUTOFF), date_field="updated"))
    list(gh.closed_prs("x/y", github._parse_ts(CUTOFF), date_field="updated"))
    assert gh.queries == [
        "repo:x/y is:pr is:merged updated:>=2026-07-04T00:00:00+00:00 sort:updated-desc",
        "repo:x/y is:pr is:closed is:unmerged updated:>=2026-07-04T00:00:00+00:00 sort:updated-desc",
    ]


RAW_PR = {
    "number": 7, "title": "T", "url": "https://github.com/x/y/pull/7",
    "createdAt": "2026-07-10T00:00:00Z", "updatedAt": "2026-07-10T01:00:00Z", "closedAt": None, "mergedAt": None,
    "author": None,
    "labels": {"nodes": [{"name": "pr-bugfix"}]},
    "files": {"nodes": [{"path": "src/a.py"}]},
}


def test_parse_pr():
    pr = github._parse_pr(RAW_PR)
    assert pr.number == 7
    assert pr.author == "ghost"
    assert pr.merged_at is None
    assert pr.files == ["src/a.py"]
    assert pr.labels == ["pr-bugfix"]


def test_pr_fetch():
    class FakePRGH(github.GitHub):
        def __init__(self, node):
            super().__init__(config.GithubConfig(token="x"))
            self.node = node

        def _graphql(self, query, variables):
            return {"repository": {"pullRequest": self.node}}

    assert FakePRGH(RAW_PR).pr("x/y", 7).number == 7
    assert FakePRGH(None).pr("x/y", 7) is None
