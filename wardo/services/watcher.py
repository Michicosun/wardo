import datetime
import logging
import threading
import time

from ..clients import github, telegram
from ..config import config
from . import utils

log = logging.getLogger("wardo.watcher")

SINCE_SAFETY_MARGIN = datetime.timedelta(hours=1)


def _pr_message(event: str, repo: str, pr: github.PRInfo, components: list[str]) -> str:
    return (f"{event}\n"
            f"{utils.pr_message(pr, repo, components)}")


def _prune(seen, horizon):
    return {number: ts for number, ts in seen.items() if ts >= horizon}


class Watcher:
    def __init__(self, cfg: config.Config) -> None:
        self.gh = github.GitHub(cfg.github)
        self.tg = telegram.Telegram(cfg.telegram)
        self.repos = cfg.wardo.repositories
        self.poll_interval = cfg.wardo.poll_interval
        self.owner_id = cfg.wardo.allowed_user_id
        self.boot = utils.now()
        self.since = {r.repo: self.boot for r in self.repos}
        self.notified_open: dict[str, dict] = {r.repo: {} for r in self.repos}
        self.notified_merged: dict[str, dict] = {r.repo: {} for r in self.repos}
        self.notified_closed: dict[str, dict] = {r.repo: {} for r in self.repos}

    def _notify(self, r, prs, seen, event_ts, event):
        for pr in prs:
            if pr.number in seen:
                continue

            ts = event_ts(pr)
            seen[pr.number] = ts

            if ts <= self.boot or not utils.is_pr_matched(pr, r):
                continue

            log.info("%s #%s in %s", event, pr.number, r.repo)
            self.tg.send(self.owner_id, _pr_message(event, r.repo, pr, utils.matched_components(pr, r.components)))

    def _round(self) -> None:
        started = utils.now()

        log.info("started watcher round at %s", started)
        for r in self.repos:
            try:
                cutoff = self.since[r.repo] - SINCE_SAFETY_MARGIN
                self._notify(r, self.gh.open_prs(r.repo, cutoff), self.notified_open[r.repo], lambda pr: pr.created_at, "🔴 New")
                self._notify(r, self.gh.merged_prs(r.repo, cutoff, date_field="updated"), self.notified_merged[r.repo], lambda pr: pr.merged_at, "🟣 Merged")
                self._notify(r, self.gh.closed_prs(r.repo, cutoff, date_field="updated"), self.notified_closed[r.repo], lambda pr: pr.closed_at, "🟢 Closed")

                horizon = started - SINCE_SAFETY_MARGIN
                self.since[r.repo] = started
                self.notified_open[r.repo] = _prune(self.notified_open[r.repo], horizon)
                self.notified_merged[r.repo] = _prune(self.notified_merged[r.repo], horizon)
                self.notified_closed[r.repo] = _prune(self.notified_closed[r.repo], horizon)
                log.info("updated %s", r.repo)

            except Exception:
                log.exception("poll failed for %s", r.repo)

    def _loop(self) -> None:
        while True:
            self._round()
            time.sleep(self.poll_interval)

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()
