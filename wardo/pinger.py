import datetime
import logging
import threading
import time

import croniter

from . import telegram

log = logging.getLogger("wardo.pinger")

PING_TEXT = "✅ Wardo is alive"


def now():
    return datetime.datetime.now(datetime.timezone.utc)


class Pinger:
    def __init__(self, cfg):
        self.tg = telegram.Telegram(cfg.telegram)
        self.owner_id = cfg.wardo.allowed_user_id
        self.schedule = croniter.croniter(cfg.wardo.ping_schedule, now())

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def ping(self):
        log.info("ping")
        self.tg.send(self.owner_id, PING_TEXT)

    def _loop(self):
        while True:
            wakeup = self.schedule.get_next(datetime.datetime)
            time.sleep(max((wakeup - now()).total_seconds(), 0))
            self.ping()
