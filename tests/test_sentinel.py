import datetime

from wardo.clients import github
from wardo.config import config
from wardo.services import sentinel, utils, watcher

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    wardo=config.WardoConfig(poll_interval=60, stall_interval=600, check_interval=60, ping_schedule="0 9 * * *", allowed_user_id=42,
                             repositories=[config.Repository(repo="x/y", components=[config.Component(name="core", paths=["src/"])],
                                                             title_filters=[], label_filters=[]),
                                           config.Repository(repo="x/z", components=[config.Component(name="core", paths=["src/"])],
                                                             title_filters=[], label_filters=[])]),
)

NOW = github._parse_ts("2026-07-10T12:00:00Z")


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def make_sentinel(monkeypatch):
    monkeypatch.setattr(utils, "now", lambda: NOW)
    s = sentinel.Sentinel(CFG, watcher.Watcher(CFG))
    s.tg = FakeTG()
    return s


def test_fresh_sync_does_not_alert(monkeypatch):
    s = make_sentinel(monkeypatch)
    s.watcher_bot.since = {"x/y": NOW - datetime.timedelta(seconds=599), "x/z": NOW}

    s._check()

    assert s.tg.sent == []


def test_stale_repo_alerts_once(monkeypatch):
    s = make_sentinel(monkeypatch)
    stale_since = NOW - datetime.timedelta(seconds=601)
    s.watcher_bot.since = {"x/y": stale_since, "x/z": NOW}

    s._check()
    s._check()

    assert len(s.tg.sent) == 1
    chat_id, text = s.tg.sent[0]
    assert chat_id == 42
    assert "⚠️ Watcher stalled" in text
    assert "x/y" in text and "x/z" not in text
    assert "2026-07-10 11:49:59 UTC" in text


def test_recovery_notifies_and_rearms(monkeypatch):
    s = make_sentinel(monkeypatch)
    s.watcher_bot.since = {"x/y": NOW - datetime.timedelta(seconds=601)}

    s._check()
    s.watcher_bot.since = {"x/y": NOW}
    s._check()
    s._check()
    s.watcher_bot.since = {"x/y": NOW - datetime.timedelta(seconds=601)}
    s._check()

    texts = [t for _, t in s.tg.sent]
    assert len(texts) == 3
    assert "⚠️ Watcher stalled" in texts[0]
    assert "✅ Watcher recovered" in texts[1] and "x/y" in texts[1]
    assert "⚠️ Watcher stalled" in texts[2]


def test_each_stale_repo_alerts(monkeypatch):
    s = make_sentinel(monkeypatch)
    s.watcher_bot.since = {"x/y": NOW - datetime.timedelta(seconds=601),
                           "x/z": NOW - datetime.timedelta(seconds=700)}

    s._check()

    assert len(s.tg.sent) == 2
