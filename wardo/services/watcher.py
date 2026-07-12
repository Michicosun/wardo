import datetime
import logging
import threading
import time

from ..clients import github, telegram
from . import utils

log = logging.getLogger("wardo.watcher")

SINCE_SAFETY_MARGIN = datetime.timedelta(hours=1)


def _pr_message(event, repo, pr):
    return (f"{event} in {repo}\n"
            f"{utils.pr_line(pr)}")


def _prune(seen, horizon):
    return {number: ts for number, ts in seen.items() if ts >= horizon}


class Watcher:
    def __init__(self, cfg):
        self.gh = github.GitHub(cfg.github)
        self.tg = telegram.Telegram(cfg.telegram)
        self.repos = cfg.wardo.repositories
        self.poll_interval = cfg.wardo.poll_interval
        self.owner_id = cfg.wardo.allowed_user_id
        self.boot = utils.now()
        self.since = {r.repo: self.boot for r in self.repos}
        self.notified_open = {r.repo: {} for r in self.repos}
        self.notified_merged = {r.repo: {} for r in self.repos}

    def _notify(self, r, prs, seen, event_ts, event):
        for pr in prs:
            if pr.number in seen:
                continue

            ts = event_ts(pr)
            seen[pr.number] = ts

            if ts <= self.boot or not utils.is_pr_matched(pr, r):
                continue

            log.info("%s #%s in %s", event, pr.number, r.repo)
            self.tg.send(self.owner_id, _pr_message(event, r.repo, pr))

    def _round(self):
        started = utils.now()

        log.info("started watcher round at %s", started)
        for r in self.repos:
            try:
                cutoff = self.since[r.repo] - SINCE_SAFETY_MARGIN
                self._notify(r, self.gh.new_prs(r.repo, cutoff), self.notified_open[r.repo], lambda pr: pr.created_at, "🆕 New PR")
                self._notify(r, self.gh.closed_prs(r.repo, cutoff), self.notified_merged[r.repo], lambda pr: pr.merged_at, "🔀 Merged PR")

                horizon = started - SINCE_SAFETY_MARGIN
                self.since[r.repo] = started
                self.notified_open[r.repo] = _prune(self.notified_open[r.repo], horizon)
                self.notified_merged[r.repo] = _prune(self.notified_merged[r.repo], horizon)
                log.info("updated %s", r.repo)

            except Exception:
                log.exception("poll failed for %s", r.repo)

    def _loop(self):
        while True:
            self._round()
            time.sleep(self.poll_interval)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
