from wardo import config, github


class FakeGH(github.GitHub):
    def __init__(self, nodes):
        super().__init__(config.GithubConfig(token="x"))
        self.nodes = nodes
        self.served = 0

    def _pull_requests(self, repo, states, order, page_size=100):
        for n in self.nodes:
            self.served += 1
            yield n


def test_is_pr_watched(node):
    pr = node(files=["src/a.py", "docs/b.md", "src/deep/c.py"])
    assert github._is_pr_watched(pr, ["src/", "lib/"])
    assert github._is_pr_watched(pr, ["docs/"])
    assert not github._is_pr_watched(pr, ["lib/"])


def test_new_prs_filters_and_stops(node):
    since = github._parse_ts("2026-07-10T00:00:00Z")
    gh = FakeGH([
        node(number=4, created="2026-07-11T00:00:00Z", files=["src/a.py"]),
        node(number=3, created="2026-07-10T12:00:00Z", files=["docs/x.md"]),
        node(number=2, created="2026-07-09T00:00:00Z", files=["src/b.py"]),
        node(number=1, created="2026-07-08T00:00:00Z", files=["src/c.py"]),
    ])
    result = gh.new_prs("x/y", ["src/"], since)
    assert [pr.number for pr in result] == [4]
    assert gh.served == 3


def test_active_prs(node):
    gh = FakeGH([
        node(number=2, files=["src/a.py"], sub=True),
        node(number=1, files=["docs/x.md"]),
    ])
    result = gh.active_prs("x/y", ["src/"])
    assert [pr.number for pr in result] == [2]
    assert result[0].subscribed


def test_closed_prs_cutoff_and_stop(node):
    cutoff = github._parse_ts("2026-07-04T00:00:00Z")
    gh = FakeGH([
        node(number=5, merged="2026-07-10T00:00:00Z", updated="2026-07-10T00:00:00Z", files=["src/a.py"]),
        node(number=4, merged="2026-07-09T00:00:00Z", updated="2026-07-09T12:00:00Z", files=["docs/x.md"]),
        node(number=3, merged="2026-07-01T00:00:00Z", updated="2026-07-08T00:00:00Z", files=["src/b.py"]),
        node(number=2, merged="2026-07-02T00:00:00Z", updated="2026-07-02T00:00:00Z", files=["src/c.py"]),
        node(number=1, merged="2026-07-03T00:00:00Z", updated="2026-07-03T00:00:00Z", files=["src/d.py"]),
    ])
    result = gh.closed_prs("x/y", ["src/"], cutoff)
    assert [pr.number for pr in result] == [5]
    assert gh.served == 4


def test_parse_pr():
    raw = {
        "number": 7, "title": "T", "url": "https://github.com/x/y/pull/7",
        "createdAt": "2026-07-10T00:00:00Z", "updatedAt": "2026-07-10T01:00:00Z", "mergedAt": None,
        "author": None,
        "viewerSubscription": "SUBSCRIBED",
        "files": {"nodes": [{"path": "src/a.py"}]},
    }
    pr = github._parse_pr(raw)
    assert pr.number == 7
    assert pr.author == "ghost"
    assert pr.subscribed
    assert pr.merged_at is None
    assert pr.files == ["src/a.py"]
