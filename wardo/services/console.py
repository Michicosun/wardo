import datetime
import html
import logging
import re

from ..clients import github, telegram
from ..config import config
from . import pinger, watcher, utils

log = logging.getLogger("wardo.console")

PROGRESS_EVERY = 100


def _format_ts(ts: datetime.datetime | None) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "never"


def _parse_days(arg: str) -> int:
    try:
        days = int(arg)
    except ValueError:
        return 1

    return days if days > 0 else 1


class Console:
    def __init__(self, cfg: config.Config, watcher_bot: watcher.Watcher, pinger_bot: pinger.Pinger) -> None:
        self.gh = github.GitHub(cfg.github)
        self.tg = telegram.Telegram(cfg.telegram)
        self.repos = cfg.wardo.repositories
        self.poll_interval = cfg.wardo.poll_interval
        self.owner_id = cfg.wardo.allowed_user_id
        self.watcher_bot = watcher_bot
        self.pinger_bot = pinger_bot

    def _stream_prs(self, chat_id, header, prs, repo):
        self.tg.send(chat_id, header)

        found = processed = 0
        for pr in prs:
            processed += 1
            if processed % PROGRESS_EVERY == 0:
                self.tg.send(chat_id, f"Processed {processed} PRs…")

            if not utils.is_pr_matched(pr, repo):
                continue

            found += 1
            self.tg.send(chat_id, utils.pr_message(pr, repo.repo, utils.matched_components(pr, repo.components)))

        if not found:
            self.tg.send(chat_id, "Nothing found")
        else:
            self.tg.send(chat_id, f"Search finished. Processed {processed} PRs")

    def serve(self) -> None:
        for msg in self.tg.updates():
            try:
                self.handle(msg)
            except Exception:
                log.exception("failed to handle message")

    def handle(self, msg: telegram.Message) -> None:
        if msg.user_id != self.owner_id:
            log.warning("unauthorized access: id=%s username=%s text=%r", msg.user_id, msg.username, msg.text)
            self.tg.send(msg.chat_id, "Unauthorized access.")
            return

        log.info("command from owner: %r", msg.text)

        parts = msg.text.split()
        cmd = parts[0].split("@")[0] if parts else ""
        try:
            if cmd == "/open":
                self.cmd_open(msg.chat_id, parts[1] if len(parts) > 1 else "")
            elif cmd == "/merged":
                self.cmd_merged(msg.chat_id, parts[1] if len(parts) > 1 else "")
            elif cmd == "/closed":
                self.cmd_closed(msg.chat_id, parts[1] if len(parts) > 1 else "")
            elif cmd == "/check":
                self.cmd_check(msg.chat_id, parts[1] if len(parts) > 1 else "")
            elif cmd == "/info":
                self.cmd_info(msg.chat_id)
            elif cmd in ("/start", "/help"):
                self.cmd_help(msg.chat_id)
            else:
                self.cmd_unknown(msg.chat_id)
        except Exception as e:
            log.exception("command failed: %r", msg.text)
            self.tg.send(msg.chat_id, f"Command failed: {html.escape(str(e))}")

    def cmd_open(self, chat_id: int, arg: str) -> None:
        days = _parse_days(arg)
        cutoff = utils.now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — open PRs in watched paths created in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.open_prs(r.repo, cutoff), r)

    def cmd_merged(self, chat_id: int, arg: str) -> None:
        days = _parse_days(arg)
        cutoff = utils.now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — PRs merged in watched paths in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.merged_prs(r.repo, cutoff), r)

    def cmd_closed(self, chat_id: int, arg: str) -> None:
        days = _parse_days(arg)
        cutoff = utils.now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — PRs closed without merge in watched paths in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.closed_prs(r.repo, cutoff), r)

    def cmd_check(self, chat_id: int, arg: str) -> None:
        ref = re.search(r"github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)", arg)
        if not ref:
            self.tg.send(chat_id, "Usage: /check [pr url]")
            return

        repo_name = f"{ref.group(1)}/{ref.group(2)}"
        repo = next((r for r in self.repos if r.repo == repo_name), None)
        if repo is None:
            self.tg.send(chat_id, f"{repo_name} is not watched")
            return

        pr = self.gh.pr(repo_name, int(ref.group(3)))
        if pr is None:
            self.tg.send(chat_id, "PR not found")
            return

        components = utils.matched_components(pr, repo.components)
        matched = html.escape(", ".join(components))
        lines = [utils.pr_message(pr, repo_name, components),
                 "",
                 f"<b>components:</b> {f'✅ {matched}' if components else '❌ not matched'}",
                 f"<b>title filters:</b> {'❌ filtered out' if utils.is_title_filtered(pr, repo.title_filters) else '✅ passed'}",
                 f"<b>label filters:</b> {'❌ filtered out' if utils.is_label_filtered(pr, repo.label_filters) else '✅ passed'}",
                 "",
                 f"<b>Verdict:</b> {'✅ would be notified' if utils.is_pr_matched(pr, repo) else '❌ would be hidden'}"]

        self.tg.send_lines(chat_id, lines)

    def cmd_info(self, chat_id: int) -> None:
        lines = [f"<b>now:</b> {_format_ts(utils.now())}",
                 f"<b>last ping:</b> {_format_ts(self.pinger_bot.last_ping)}",
                 f"<b>next ping:</b> {_format_ts(self.pinger_bot.next_ping)}",
                 "",
                 f"<b>poll interval:</b> {self.poll_interval}s",
                 ""]

        for r in self.repos:
            lines.append(f"<b>{r.repo}</b> (up to: {_format_ts(self.watcher_bot.since.get(r.repo))}):")

            lines.append("  <b>components:</b>")
            for component in r.components:
                lines.append(f"    <b>{html.escape(component.name)}:</b>")
                lines += [f"      {html.escape(str(p))}" for p in component.paths]

            if r.title_filters:
                lines.append("  <b>title filters:</b>")
                lines += [f"    {html.escape(str(t))}" for t in r.title_filters]

            if r.label_filters:
                lines.append("  <b>label filters:</b>")
                lines += [f"    {html.escape(str(t))}" for t in r.label_filters]

            lines.append("")

        self.tg.send_lines(chat_id, lines)

    def cmd_help(self, chat_id: int) -> None:
        lines = ["/open [days] — open PRs created in the last [days] days (default 1)",
                 "/merged [days] — PRs merged in the last [days] days (default 1)",
                 "/closed [days] — PRs closed without merge in the last [days] days (default 1)",
                 "/check [pr url] — explain why a PR is shown or hidden",
                 "/info — watched repositories and settings",
                 "/help — this message"]

        self.tg.send_lines(chat_id, lines)

    def cmd_unknown(self, chat_id: int) -> None:
        self.tg.send(chat_id, "Unknown command, try /help")
