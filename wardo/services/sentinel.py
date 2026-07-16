import datetime
import logging
import threading
import time

from ..clients import telegram
from ..config import config
from . import utils, watcher

log = logging.getLogger("wardo.sentinel")


def _format_ts(ts: datetime.datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


def _alert_message(repo: str, since: datetime.datetime) -> str:
    return ("⚠️ Watcher stalled\n"
            f"<b>Repository:</b> {repo}\n"
            f"<b>Last successful sync:</b> {_format_ts(since)}")


def _recovered_message(repo: str, since: datetime.datetime) -> str:
    return ("✅ Watcher recovered\n"
            f"<b>Repository:</b> {repo}\n"
            f"<b>Last successful sync:</b> {_format_ts(since)}")


def _is_fresh(since: datetime.datetime, threshold: datetime.timedelta) -> bool:
    return utils.now() - since <= threshold


class Sentinel:
    def __init__(self, cfg: config.Config, watcher_bot: watcher.Watcher) -> None:
        self.tg = telegram.Telegram(cfg.telegram)
        self.owner_id = cfg.wardo.allowed_user_id
        self.check_interval = cfg.wardo.check_interval
        self.threshold = datetime.timedelta(seconds=cfg.wardo.stall_interval)
        self.watcher_bot = watcher_bot
        self.alerted: set[str] = set()

    def _recover(self, repo: str, since: datetime.datetime) -> None:
        self.alerted.discard(repo)
        log.info("watcher recovered for %s: last successful sync at %s", repo, since)
        self.tg.send(self.owner_id, _recovered_message(repo, since))

    def _alert(self, repo: str, since: datetime.datetime) -> None:
        self.alerted.add(repo)
        log.warning("watcher stalled for %s: last successful sync at %s", repo, since)
        self.tg.send(self.owner_id, _alert_message(repo, since))

    def _check(self) -> None:
        for repo, since in self.watcher_bot.since.items():
            if _is_fresh(since, self.threshold):
                if repo in self.alerted:
                    self._recover(repo, since)

                continue

            if repo not in self.alerted:
                self._alert(repo, since)

    def _loop(self) -> None:
        while True:
            time.sleep(self.check_interval)
            try:
                self._check()
            except Exception:
                log.exception("sentinel check failed")

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()
