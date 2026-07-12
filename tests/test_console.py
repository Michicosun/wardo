from wardo.config import config
from wardo.services import console, pinger, utils, watcher

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

    def send_lines(self, chat_id, lines):
        self.sent.append((chat_id, "\n".join(lines)))


def make_bot():
    b = console.Console(CFG, watcher.Watcher(CFG), pinger.Pinger(CFG))
    b.tg = FakeTG()
    return b


def msg(uid, text):
    return {"from": {"id": uid, "username": "u"}, "chat": {"id": uid}, "text": text}


def test_unauthorized():
    b = make_bot()
    b.handle(msg(7, "/open"))
    assert b.tg.sent == [(7, "Unauthorized access.")]


def test_help():
    b = make_bot()
    b.handle(msg(42, "/help"))
    text = b.tg.sent[0][1]
    assert "/open" in text and "/merged" in text and "/info" in text
    assert "x/y" not in text


def test_info():
    b = make_bot()
    b.handle(msg(42, "/info"))
    text = b.tg.sent[0][1]
    assert "<b>poll interval:</b> 5s" in text
    assert "<b>last ping:</b> never" in text
    assert "<b>next ping:</b>" in text and "<b>next ping:</b> never" not in text
    assert "<b>x/y</b> (up to:" in text and "src/" in text


def test_info_shows_title_filters(monkeypatch):
    b = make_bot()
    b.handle(msg(42, "/info"))
    assert "title filters:" not in b.tg.sent[0][1]

    monkeypatch.setattr(b.repos[0], "title_filters", ["^Backport"])
    b.handle(msg(42, "/info"))
    assert "title filters:" in b.tg.sent[1][1] and "^Backport" in b.tg.sent[1][1]


def test_info_with_activity():
    b = make_bot()
    b.pinger_bot.last_ping = utils.now()
    b.handle(msg(42, "/info"))
    text = b.tg.sent[0][1]
    assert "never" not in text
    assert text.count("UTC") == 3


def test_unknown_command():
    b = make_bot()
    b.handle(msg(42, "hello"))
    assert "Unknown command" in b.tg.sent[0][1]


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


def test_open_with_days(node):
    b = make_bot()
    seen = {}
    b.gh.open_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/open 7"))
    assert (utils.now() - seen["cutoff"]).days == 7
    assert "last 7 day(s)" in b.tg.sent[0][1]
    assert b.tg.sent[1][1] == "Nothing found"


def test_progress_reports(node):
    b = make_bot()
    b.gh.open_prs = lambda repo, cutoff: [node(files=["docs/x.md"])] * 250
    b.handle(msg(42, "/open"))
    texts = [t for _, t in b.tg.sent]
    assert texts.count("Processed 100 PRs…") == 1
    assert texts.count("Processed 200 PRs…") == 1
    assert texts[-1] == "Nothing found"


def test_open_bad_arg_falls_back_to_default(node):
    b = make_bot()
    seen = {}
    b.gh.open_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/open nope"))
    assert (utils.now() - seen["cutoff"]).days == 1
    assert "last 1 day(s)" in b.tg.sent[0][1]


def test_command_failure_is_reported(node):
    b = make_bot()

    def boom(repo, cutoff):
        raise RuntimeError("github down")

    b.gh.open_prs = boom
    b.handle(msg(42, "/open"))
    assert b.tg.sent[-1][1] == "Command failed: github down"


def test_merged(node):
    b = make_bot()
    seen = {}
    b.gh.merged_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/merged 7"))
    assert (utils.now() - seen["cutoff"]).days == 7
    assert "merged" in b.tg.sent[0][1] and "last 7 day(s)" in b.tg.sent[0][1]
    assert b.tg.sent[1][1] == "Nothing found"


def test_closed(node):
    b = make_bot()
    seen = {}
    b.gh.closed_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/closed 7"))
    assert (utils.now() - seen["cutoff"]).days == 7
    assert "closed without merge" in b.tg.sent[0][1] and "last 7 day(s)" in b.tg.sent[0][1]
    assert b.tg.sent[1][1] == "Nothing found"
