import datetime

from wardo.config import config
from wardo.services import pinger

CFG = config.Config(
    github=config.GithubConfig(token="x"),
    telegram=config.TelegramConfig(token="y"),
    wardo=config.WardoConfig(poll_interval=5, ping_schedule="0 9 * * *",
                             allowed_user_id=42, repositories=[]),
)


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def test_ping():
    p = pinger.Pinger(CFG)
    p.tg = FakeTG()
    assert p.last_ping is None
    p._ping()
    assert p.tg.sent == [(42, pinger.PING_TEXT)]
    assert p.last_ping is not None


def test_ping_failure_is_contained():
    p = pinger.Pinger(CFG)

    class BrokenTG:
        def send(self, chat_id, text):
            raise RuntimeError("network down")

    p.tg = BrokenTG()
    p._ping()
    assert p.last_ping is None


def test_schedule_follows_cron():
    p = pinger.Pinger(CFG)
    assert (p.next_ping.hour, p.next_ping.minute) == (9, 0)
    following = p.schedule.get_next(datetime.datetime)
    assert following - p.next_ping == datetime.timedelta(days=1)
