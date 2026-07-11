from wardo import config, console

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    watcher=config.WatcherConfig(poll_interval=5, allowed_user_id=42,
                                 repositories=[config.Repository(repo="x/y", paths=["src/"])]),
)


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    def send_lines(self, chat_id, lines):
        self.sent.append((chat_id, "\n".join(lines)))


def make_bot():
    b = console.Console(CFG)
    b.tg = FakeTG()
    return b


def msg(uid, text):
    return {"from": {"id": uid, "username": "u"}, "chat": {"id": uid}, "text": text}


def test_unauthorized():
    b = make_bot()
    b.handle(msg(7, "/active"))
    assert b.tg.sent == [(7, "Unauthorized access.")]


def test_help():
    b = make_bot()
    b.handle(msg(42, "/help"))
    text = b.tg.sent[0][1]
    assert "/active" in text and "/closed" in text and "x/y" in text


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


def test_active(node):
    b = make_bot()
    seen = {}
    b.gh.active_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and [node()]
    b.handle(msg(42, "/active"))
    assert (console.now() - seen["cutoff"]).days == 1
    header, row = b.tg.sent[0][1], b.tg.sent[1][1]
    assert "x/y" in header and "last 1 day(s)" in header
    assert "alice" in row and "https://github.com/x/y/pull/1" in row
    assert b.tg.sent[2][1] == "Search finished. Processed 1 PRs"


def test_active_with_days(node):
    b = make_bot()
    seen = {}
    b.gh.active_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/active 7"))
    assert (console.now() - seen["cutoff"]).days == 7
    assert "last 7 day(s)" in b.tg.sent[0][1]
    assert b.tg.sent[1][1] == "Nothing found"


def test_progress_reports(node):
    b = make_bot()
    b.gh.active_prs = lambda repo, cutoff: [node(files=["docs/x.md"])] * 250
    b.handle(msg(42, "/active"))
    texts = [t for _, t in b.tg.sent]
    assert texts.count("Processed 100 PRs…") == 1
    assert texts.count("Processed 200 PRs…") == 1
    assert texts[-1] == "Nothing found"


def test_active_bad_arg_falls_back_to_default(node):
    b = make_bot()
    seen = {}
    b.gh.active_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/active nope"))
    assert (console.now() - seen["cutoff"]).days == 1
    assert "last 1 day(s)" in b.tg.sent[0][1]


def test_closed(node):
    b = make_bot()
    seen = {}
    b.gh.closed_prs = lambda repo, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/closed 7"))
    assert (console.now() - seen["cutoff"]).days == 7
    assert "merged" in b.tg.sent[0][1] and "last 7 day(s)" in b.tg.sent[0][1]
    assert b.tg.sent[1][1] == "Nothing found"
