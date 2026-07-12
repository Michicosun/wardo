import datetime
import html
import logging

from ..clients import github, telegram
from . import utils

log = logging.getLogger("wardo.console")

PROGRESS_EVERY = 100


def _format_ts(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "never"


def _parse_days(arg):
    try:
        days = int(arg)
    except ValueError:
        return 1

    return days if days > 0 else 1


def _unpack_request_msg(msg):
    user = msg.get("from", {})
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    return user.get("id"), user.get("username"), chat_id, text


class Console:
    def __init__(self, cfg, watcher_bot, pinger_bot):
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
            self.tg.send(chat_id, utils.pr_line(pr))

        if not found:
            self.tg.send(chat_id, "Nothing found")
        else:
            self.tg.send(chat_id, f"Search finished. Processed {processed} PRs")

    def serve(self):
        for msg in self.tg.updates():
            try:
                self.handle(msg)
            except Exception:
                log.exception("failed to handle message")

    def handle(self, msg):
        uid, username, chat_id, text = _unpack_request_msg(msg)

        if uid != self.owner_id:
            log.warning("unauthorized access: id=%s username=%s text=%r", uid, username, text)
            self.tg.send(chat_id, "Unauthorized access.")
            return

        log.info("command from owner: %r", text)

        parts = text.split()
        cmd = parts[0].split("@")[0] if parts else ""
        try:
            if cmd == "/open":
                self.cmd_open(chat_id, parts[1] if len(parts) > 1 else "")
            elif cmd == "/merged":
                self.cmd_merged(chat_id, parts[1] if len(parts) > 1 else "")
            elif cmd == "/closed":
                self.cmd_closed(chat_id, parts[1] if len(parts) > 1 else "")
            elif cmd == "/info":
                self.cmd_info(chat_id)
            elif cmd in ("/start", "/help"):
                self.cmd_help(chat_id)
            else:
                self.cmd_unknown(chat_id)
        except Exception as e:
            log.exception("command failed: %r", text)
            self.tg.send(chat_id, f"Command failed: {html.escape(str(e))}")

    def cmd_open(self, chat_id, arg):
        days = _parse_days(arg)
        cutoff = utils.now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — open PRs in watched paths created in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.open_prs(r.repo, cutoff), r)

    def cmd_merged(self, chat_id, arg):
        days = _parse_days(arg)
        cutoff = utils.now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — PRs merged in watched paths in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.merged_prs(r.repo, cutoff), r)

    def cmd_closed(self, chat_id, arg):
        days = _parse_days(arg)
        cutoff = utils.now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — PRs closed without merge in watched paths in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.closed_prs(r.repo, cutoff), r)

    def cmd_help(self, chat_id):
        lines = ["/open [days] — open PRs created in the last [days] days (default 1)",
                 "/merged [days] — PRs merged in the last [days] days (default 1)",
                 "/closed [days] — PRs closed without merge in the last [days] days (default 1)",
                 "/info — watched repositories and settings",
                 "/help — this message"]

        self.tg.send_lines(chat_id, lines)

    def cmd_info(self, chat_id):
        lines = [f"<b>last ping:</b> {_format_ts(self.pinger_bot.last_ping)}",
                 f"<b>next ping:</b> {_format_ts(self.pinger_bot.next_ping)}",
                 "",
                 f"<b>poll interval:</b> {self.poll_interval}s",
                 ""]

        for r in self.repos:
            lines.append(f"<b>{r.repo}</b> (up to: {_format_ts(self.watcher_bot.since.get(r.repo))}):")

            lines.append("  <b>paths:</b>")
            lines += [f"    {html.escape(str(p))}" for p in r.paths]

            if r.title_filters:
                lines.append("  <b>title filters:</b>")
                lines += [f"    {html.escape(str(t))}" for t in r.title_filters]

            if r.label_filters:
                lines.append("  <b>label filters:</b>")
                lines += [f"    {html.escape(str(t))}" for t in r.label_filters]

            lines.append("")

        self.tg.send_lines(chat_id, lines)

    def cmd_unknown(self, chat_id):
        self.tg.send(chat_id, "Unknown command, try /help")
