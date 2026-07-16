import pytest

from wardo.clients import telegram
from wardo.config import config
from wardo.services import console, pinger, utils, watcher

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    wardo=config.WardoConfig(poll_interval=5, stall_interval=50, check_interval=5, ping_schedule="0 9 * * *", allowed_user_id=42,
                             repositories=[config.Repository(repo="x/y", components=[config.Component(name="core", paths=["src/"])],
                                                             title_filters=[], label_filters=[])]),
)


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    def send_lines(self, chat_id, lines):
        self.sent.append((chat_id, "\n".join(lines)))


def make_bot():
    b = console.Console(CFG, watcher.Watcher(CFG), pinger.Pinger(CFG))
    b.tg = FakeTG()
    return b


def msg(uid, text):
    return telegram.Message(user_id=uid, username="u", chat_id=uid, text=text)


def test_parse_message():
    raw = {"from": {"id": 42, "username": "u"}, "chat": {"id": 7}, "text": " /open "}
    assert telegram._parse_message(raw) == telegram.Message(user_id=42, username="u", chat_id=7, text="/open")
    assert telegram._parse_message({"chat": {"id": 7}}) == telegram.Message(user_id=None, username=None, chat_id=7, text="")


def test_unauthorized():
    b = make_bot()
    b.handle(msg(7, "/open"))
    assert b.tg.sent == [(7, "Unauthorized access.")]


def test_help_and_unknown_command():
    b = make_bot()
    b.handle(msg(42, "/help"))
    text = b.tg.sent[0][1]
    assert "/open" in text and "/merged" in text and "/closed" in text and "/info" in text
    assert "x/y" not in text

    b.handle(msg(42, "hello"))
    assert "Unknown command" in b.tg.sent[1][1]


def test_info(monkeypatch):
    b = make_bot()
    b.handle(msg(42, "/info"))
    text = b.tg.sent[0][1]
    assert "<b>now:</b> never" not in text and "<b>now:</b>" in text
    assert "<b>poll interval:</b> 5s" in text
    assert "<b>last ping:</b> never" in text
    assert "<b>next ping:</b>" in text and "<b>next ping:</b> never" not in text
    assert "<b>x/y</b> (up to:" in text and "src/" in text
    assert "title filters:" not in text and "label filters:" not in text

    b.pinger_bot.last_ping = utils.now()
    monkeypatch.setattr(b.repos[0], "title_filters", ["^Backport"])
    monkeypatch.setattr(b.repos[0], "label_filters", ["pr-backport"])
    b.handle(msg(42, "/info"))
    text = b.tg.sent[1][1]
    assert "never" not in text and text.count("UTC") == 4
    assert "title filters:" in text and "^Backport" in text
    assert "label filters:" in text and "pr-backport" in text


def test_parse_days():
    assert console._parse_days("7") == 7
    assert console._parse_days("") == 1
    assert console._parse_days("nope") == 1
    assert console._parse_days("-3") == 1
    assert console._parse_days("0") == 1


def test_open(node):
    b = make_bot()
    seen = {}
    b.gh.open_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and [node()]
    b.handle(msg(42, "/open"))
    assert (utils.now() - seen["cutoff"]).days == 1
    header, row = b.tg.sent[0][1], b.tg.sent[1][1]
    assert "x/y" in header and "last 1 day(s)" in header
    assert "alice" in row and "https://github.com/x/y/pull/1" in row
    assert b.tg.sent[2][1] == "Search finished. Processed 1 PRs"

    seen.clear()
    b.gh.open_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/open 7"))
    assert (utils.now() - seen["cutoff"]).days == 7
    assert "last 7 day(s)" in b.tg.sent[3][1]
    assert b.tg.sent[4][1] == "Nothing found"


@pytest.mark.parametrize("cmd, method, phrase", [
    ("/merged 7", "merged_prs", "merged"),
    ("/closed 7", "closed_prs", "closed without merge"),
])
def test_merged_and_closed(node, cmd, method, phrase):
    b = make_bot()
    seen = {}
    setattr(b.gh, method, lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and [])
    b.handle(msg(42, cmd))
    assert (utils.now() - seen["cutoff"]).days == 7
    assert phrase in b.tg.sent[0][1] and "last 7 day(s)" in b.tg.sent[0][1]
    assert b.tg.sent[1][1] == "Nothing found"


def test_check(node):
    b = make_bot()
    b.handle(msg(42, "/check nonsense"))
    assert "Usage" in b.tg.sent[0][1]

    b.handle(msg(42, "/check https://github.com/a/b/pull/5"))
    assert b.tg.sent[1][1] == "a/b is not watched"

    b.gh.pr = lambda repo, number: None
    b.handle(msg(42, "/check https://github.com/x/y/pull/5"))
    assert b.tg.sent[2][1] == "PR not found"

    b.gh.pr = lambda repo, number: node(title="Fix", files=["docs/x.md"])
    b.handle(msg(42, "/check https://github.com/x/y/pull/5"))
    text = b.tg.sent[3][1]
    assert "<b>components:</b> ❌ not matched" in text
    assert "<b>title filters:</b> ✅ passed" in text
    assert "<b>Verdict:</b> ❌ would be hidden" in text

    b.gh.pr = lambda repo, number: node()
    b.handle(msg(42, "/check https://github.com/x/y/pull/5"))
    text = b.tg.sent[4][1]
    assert "<b>Components:</b> core" in text
    assert "<b>components:</b> ✅ core" in text
    assert "<b>Verdict:</b> ✅ would be notified" in text


def test_progress_reports(node):
    b = make_bot()
    b.gh.open_prs = lambda repo, cutoff: [node(files=["docs/x.md"])] * 250
    b.handle(msg(42, "/open"))
    texts = [t for _, t in b.tg.sent]
    assert texts.count("Processed 100 PRs…") == 1
    assert texts.count("Processed 200 PRs…") == 1
    assert texts[-1] == "Nothing found"


def test_command_failure_is_reported(node):
    b = make_bot()

    def boom(repo, cutoff):
        raise RuntimeError("github down")

    b.gh.open_prs = boom
    b.handle(msg(42, "/open"))
    assert b.tg.sent[-1][1] == "Command failed: github down"
