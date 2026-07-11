import datetime
import html
import logging
import re
import threading
import time

from . import github, telegram

log = logging.getLogger("wardo.watcher")


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def is_pr_watched(pr, watched):
    for changed_file in pr.files:
        for watched_path in watched:
            if re.search(watched_path, changed_file):
                return True

    return False


def new_pr_message(repo, pr):
    return (f"🆕 New PR in {repo}\n"
            f"#{pr.number}: {html.escape(pr.title)}\n"
            f"author: {pr.author}\n"
            f"{pr.url}")


class Watcher:
    def __init__(self, cfg):
        self.gh = github.GitHub(cfg.github)
        self.tg = telegram.Telegram(cfg.telegram)
        self.repos = cfg.watcher.repositories
        self.poll_interval = cfg.watcher.poll_interval
        self.owner_id = cfg.console.allowed_user_id
        self.since = {r.repo: now() for r in self.repos}

    def _round(self):
        started = now()

        log.info("started watcher round at %s", started)
        for r in self.repos:
            try:
                for pr in self.gh.new_prs(r.repo, self.since[r.repo]):
                    if not is_pr_watched(pr, r.paths):
                        continue

                    log.info("new PR #%s in %s", pr.number, r.repo)
                    self.tg.send(self.owner_id, new_pr_message(r.repo, pr))

                self.since[r.repo] = started

            except Exception:
                log.exception("poll failed for %s", r.repo)


    def _loop(self):
        while True:
            self._round()
            time.sleep(self.poll_interval)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
