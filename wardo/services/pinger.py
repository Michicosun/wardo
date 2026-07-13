import datetime
import logging
import threading
import time

import croniter

from ..clients import telegram
from ..config import config
from . import utils

log = logging.getLogger("wardo.pinger")

PING_TEXT = "✅ Wardo is alive"


class Pinger:
    def __init__(self, cfg: config.Config) -> None:
        self.tg = telegram.Telegram(cfg.telegram)
        self.owner_id = cfg.wardo.allowed_user_id
        self.schedule = croniter.croniter(cfg.wardo.ping_schedule, utils.now())
        self.last_ping: datetime.datetime | None = None
        self.next_ping: datetime.datetime = self.schedule.get_next(datetime.datetime)

    def _ping(self) -> None:
        log.info("ping")
        try:
            self.tg.send(self.owner_id, PING_TEXT)
        except Exception:
            log.exception("ping failed")
            return

        self.last_ping = utils.now()

    def _loop(self) -> None:
        while True:
            time.sleep(max((self.next_ping - utils.now()).total_seconds(), 0))
            self._ping()
            self.next_ping = self.schedule.get_next(datetime.datetime)

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()
