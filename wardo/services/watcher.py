import datetime
import html
import logging
import threading
import time

from ..clients import github, telegram
from . import utils

log = logging.getLogger("wardo.watcher")

SINCE_SAFETY_MARGIN = datetime.timedelta(hours=1)


def new_pr_message(repo, pr):
    return (f"🆕 New PR in {repo}\n"
            f"#{pr.number}: {html.escape(pr.title)}\n"
            f"author: {pr.author}\n"
            f"{pr.url}")


class Watcher:
    def __init__(self, cfg):
        self.gh = github.GitHub(cfg.github)
        self.tg = telegram.Telegram(cfg.telegram)
        self.repos = cfg.wardo.repositories
        self.poll_interval = cfg.wardo.poll_interval
        self.owner_id = cfg.wardo.allowed_user_id
        self.boot = utils.now()
        self.since = {r.repo: self.boot for r in self.repos}
        self.notified = {r.repo: {} for r in self.repos}

    def _round(self):
        started = utils.now()

        log.info("started watcher round at %s", started)
        for r in self.repos:
            try:
                seen = self.notified[r.repo]
                for pr in self.gh.new_prs(r.repo, self.since[r.repo] - SINCE_SAFETY_MARGIN):
                    if pr.number in seen:
                        continue

                    seen[pr.number] = pr.created_at

                    if pr.created_at <= self.boot or not utils.is_pr_matched(pr, r):
                        continue

                    log.info("new PR #%s in %s", pr.number, r.repo)
                    self.tg.send(self.owner_id, new_pr_message(r.repo, pr))

                horizon = started - SINCE_SAFETY_MARGIN
                self.since[r.repo] = started
                self.notified[r.repo] = {n: ts for n, ts in seen.items() if ts >= horizon}
                log.info("updated %s", r.repo)

            except Exception:
                log.exception("poll failed for %s", r.repo)


    def _loop(self):
        while True:
            self._round()
            time.sleep(self.poll_interval)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
