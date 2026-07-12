import pytest

from wardo.clients import github
from wardo.config import config
from wardo.services import utils, watcher

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    wardo=config.WardoConfig(poll_interval=5, ping_schedule="0 9 * * *", allowed_user_id=42,
                             repositories=[config.Repository(repo="x/y", paths=["src/"], title_filters=[], label_filters=[])]),
)


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def make_watcher(monkeypatch):
    monkeypatch.setattr(utils, "now", lambda: github._parse_ts("2026-07-10T01:00:00Z"))
    w = watcher.Watcher(CFG)
    w.tg = FakeTG()
    w.boot = github._parse_ts("2026-07-01T00:00:00Z")
    w.gh.open_prs = lambda repo, cutoff: []
    w.gh.merged_prs = lambda repo, cutoff: []
    w.gh.closed_prs = lambda repo, cutoff: []
    return w


def test_is_pr_matched(node):
    repo = config.Repository(repo="x/y",
                             paths=["src/", "QueryPlan", r"\.cpp$"],
                             title_filters=["^Backport", "Sync"],
                             label_filters=["backport", r"^ci-"])

    assert utils.is_pr_matched(node(files=["src/a.py"]), repo)
    assert utils.is_pr_matched(node(files=["lib/QueryPlan/opt.h"]), repo)
    assert utils.is_pr_matched(node(files=["lib/Data.cpp"]), repo)
    assert not utils.is_pr_matched(node(files=["docs/readme.md"]), repo)

    assert not utils.is_pr_matched(node(title="Backport #1: Fix"), repo)
    assert not utils.is_pr_matched(node(title="Auto Sync files"), repo)
    assert utils.is_pr_matched(node(title="Fix Backport logic"), repo)

    assert not utils.is_pr_matched(node(labels=["pr-backport"]), repo)
    assert not utils.is_pr_matched(node(labels=["ci-fail"]), repo)
    assert utils.is_pr_matched(node(labels=["documentation"]), repo)

    bare = config.Repository(repo="x/y", paths=["src/"], title_filters=[], label_filters=[])
    assert utils.is_pr_matched(node(title="Backport", labels=["pr-backport"]), bare)


@pytest.mark.parametrize("method, extra, event", [
    ("open_prs", {}, "New PR"),
    ("merged_prs", {"merged": "2026-07-10T00:30:00Z"}, "Merged PR"),
    ("closed_prs", {"closed": "2026-07-10T00:30:00Z"}, "Closed PR"),
])
def test_round_notifies_matched_pr_once(node, monkeypatch, method, extra, event):
    w = make_watcher(monkeypatch)
    prs = [node(number=7, **extra), node(number=8, files=["docs/x.md"], **extra)]
    setattr(w.gh, method, lambda repo, cutoff: prs)

    w._round()
    w._round()

    texts = [t for _, t in w.tg.sent]
    assert len(texts) == 1 and "pull/7" in texts[0] and event in texts[0]


def test_round_pads_cutoff_and_advances_since(monkeypatch):
    w = make_watcher(monkeypatch)
    seen = {}
    w.gh.open_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []

    w._round()

    assert seen["cutoff"] == github._parse_ts("2026-07-10T00:00:00Z")
    assert w.since["x/y"] == github._parse_ts("2026-07-10T01:00:00Z")


def test_round_skips_prs_created_before_boot(node, monkeypatch):
    w = make_watcher(monkeypatch)
    w.boot = github._parse_ts("2026-07-10T01:00:00Z")
    w.gh.open_prs = lambda repo, cutoff: [node(number=7, created="2026-07-09T00:00:00Z")]

    w._round()

    assert w.tg.sent == []
