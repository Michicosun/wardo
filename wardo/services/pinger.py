import datetime
import logging
import threading
import time

import croniter

from ..clients import telegram
from . import utils

log = logging.getLogger("wardo.pinger")

PING_TEXT = "✅ Wardo is alive"


class Pinger:
    def __init__(self, cfg):
        self.tg = telegram.Telegram(cfg.telegram)
        self.owner_id = cfg.wardo.allowed_user_id
        self.schedule = croniter.croniter(cfg.wardo.ping_schedule, utils.now())
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

        self.last_ping = utils.now()

    def _loop(self):
        while True:
            time.sleep(max((self.next_ping - utils.now()).total_seconds(), 0))
            self.ping()
            self.next_ping = self.schedule.get_next(datetime.datetime)
