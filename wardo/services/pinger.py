import datetime
import logging
import threading
import time

import croniter

from ..clients import telegram

log = logging.getLogger("wardo.pinger")

PING_TEXT = "✅ Wardo is alive"


def now():
    return datetime.datetime.now(datetime.timezone.utc)


class Pinger:
    def __init__(self, cfg):
        self.tg = telegram.Telegram(cfg.telegram)
        self.owner_id = cfg.wardo.allowed_user_id
        self.schedule = croniter.croniter(cfg.wardo.ping_schedule, now())
        self.last_ping = None
        self.next_ping = self.schedule.get_next(datetime.datetime)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def ping(self):
        log.info("ping")
        try:
            self.tg.send(self.owner_id, PING_TEXT)
        except Exception:
            log.exception("ping failed")
            return

        self.last_ping = now()

    def _loop(self):
        while True:
            time.sleep(max((self.next_ping - now()).total_seconds(), 0))
            self.ping()
            self.next_ping = self.schedule.get_next(datetime.datetime)
