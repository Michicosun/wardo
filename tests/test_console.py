from wardo import config, console

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    watcher=config.WatcherConfig(poll_interval=5,
                                 repositories=[config.Repository(repo="x/y", paths=["src/"])]),
    console=config.ConsoleConfig(allowed_user_id=42),
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


def test_closed_bad_arg():
    b = make_bot()
    for arg in ("/closed", "/closed nope", "/closed -3"):
        b.handle(msg(42, arg))
    assert [t for _, t in b.tg.sent] == ["usage: /closed &lt;days&gt;"] * 3


def test_active(node):
    b = make_bot()
    b.gh.active_prs = lambda repo, paths: [node(sub=True)]
    b.handle(msg(42, "/active"))
    text = b.tg.sent[0][1]
    assert "x/y" in text and "alice" in text and "🔔 subscribed" in text


def test_closed(node):
    b = make_bot()
    seen = {}
    b.gh.closed_prs = lambda repo, paths, cutoff: seen.setdefault("cutoff", cutoff) and []
    b.handle(msg(42, "/closed 7"))
    assert (console.now() - seen["cutoff"]).days == 7
    assert "nothing merged" in b.tg.sent[0][1]
