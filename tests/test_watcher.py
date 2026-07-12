from wardo.clients import github
from wardo.config import config
from wardo.services import utils, watcher

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    wardo=config.WardoConfig(poll_interval=5, ping_schedule="0 9 * * *", allowed_user_id=42,
                             repositories=[config.Repository(repo="x/y", paths=["src/"], title_filters=[])]),
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
    w.gh.new_prs = lambda repo, cutoff: []
    w.gh.closed_prs = lambda repo, cutoff: []
    return w


def test_is_pr_watched_prefix(node):
    pr = node(files=["src/a.py", "docs/b.md", "src/deep/c.py"])
    assert utils._is_pr_watched(pr, ["src/", "lib/"])
    assert utils._is_pr_watched(pr, ["docs/"])
    assert not utils._is_pr_watched(pr, ["lib/"])


def test_is_pr_watched_substring(node):
    pr = node(files=["src/Processors/QueryPlan/Optimizations/foo.cpp"])
    assert utils._is_pr_watched(pr, ["QueryPlan"])
    assert not utils._is_pr_watched(pr, ["MergeTree"])


def test_is_pr_watched_regex(node):
    pr = node(files=["src/Storages/MergeTree/MergeTreeData.cpp"])
    assert utils._is_pr_watched(pr, [r"MergeTree.*\.cpp$"])
    assert utils._is_pr_watched(pr, [r"^src/(Storages|Processors)/"])
    assert not utils._is_pr_watched(pr, [r"\.py$"])


def test_is_title_filtered(node):
    pr = node(title="Backport #123 to 24.3: Fix sorting")
    assert not utils._is_title_filtered(pr, [])
    assert utils._is_title_filtered(pr, ["Backport"])
    assert utils._is_title_filtered(pr, [r"^Backport #\d+"])
    assert not utils._is_title_filtered(pr, ["revert"])


def test_is_pr_matched(node):
    repo = config.Repository(repo="x/y", paths=["src/"], title_filters=["^Backport"])
    assert utils.is_pr_matched(node(title="Fix things"), repo)
    assert not utils.is_pr_matched(node(title="Backport #1: Fix things"), repo)
    assert not utils.is_pr_matched(node(title="Fix things", files=["docs/a.md"]), repo)


def test_round_notifies_watched_pr_once(node, monkeypatch):
    w = make_watcher(monkeypatch)
    w.gh.new_prs = lambda repo, cutoff: [node(number=7), node(number=8, files=["docs/x.md"])]

    w._round()
    w._round()

    texts = [t for _, t in w.tg.sent]
    assert len(texts) == 1 and "pull/7" in texts[0] and "New PR" in texts[0]
    assert w.since["x/y"] == github._parse_ts("2026-07-10T01:00:00Z")


def test_round_notifies_merged_pr_once(node, monkeypatch):
    w = make_watcher(monkeypatch)
    w.gh.closed_prs = lambda repo, cutoff: [node(number=9, merged="2026-07-10T00:30:00Z")]

    w._round()
    w._round()

    texts = [t for _, t in w.tg.sent]
    assert len(texts) == 1 and "pull/9" in texts[0] and "Merged PR" in texts[0]


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
