from wardo.clients import github
from wardo.config import config
from wardo.services import watcher

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    wardo=config.WardoConfig(poll_interval=5, ping_schedule="0 9 * * *", allowed_user_id=42,
                             repositories=[config.Repository(repo="x/y", paths=["src/"])]),
)


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def make_watcher(monkeypatch):
    monkeypatch.setattr(watcher, "now", lambda: github._parse_ts("2026-07-10T01:00:00Z"))
    w = watcher.Watcher(CFG)
    w.tg = FakeTG()
    w.boot = github._parse_ts("2026-07-01T00:00:00Z")
    return w


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


def test_round_notifies_watched_pr_once(node, monkeypatch):
    w = make_watcher(monkeypatch)
    w.gh.new_prs = lambda repo, since: [node(number=7), node(number=8, files=["docs/x.md"])]

    w._round()
    w._round()

    texts = [t for _, t in w.tg.sent]
    assert len(texts) == 1 and "#7" in texts[0]
    assert w.since["x/y"] == github._parse_ts("2026-07-10T01:00:00Z")


def test_round_pads_since_with_safety_margin(monkeypatch):
    w = make_watcher(monkeypatch)
    seen = {}
    w.gh.new_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []

    w._round()

    assert seen["cutoff"] == github._parse_ts("2026-07-10T00:00:00Z")


def test_round_skips_prs_created_before_boot(node, monkeypatch):
    w = make_watcher(monkeypatch)
    w.boot = github._parse_ts("2026-07-10T01:00:00Z")
    w.gh.new_prs = lambda repo, since: [node(number=7, created="2026-07-09T00:00:00Z")]

    w._round()

    assert w.tg.sent == []
