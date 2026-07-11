import datetime
import html
import logging

from . import github, telegram, watcher

log = logging.getLogger("wardo.console")

PROGRESS_EVERY = 100


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def link(pr):
    return f'<a href="{pr.url}">{html.escape(pr.title)}</a>'


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


def active_pr_line(pr):
    sub = "🔔 subscribed" if pr.subscribed else "🔕 not subscribed"
    return f"{link(pr)} — {pr.author} — {sub}"


def closed_pr_line(pr):
    return f"{link(pr)} — {pr.author}"


class Console:
    def __init__(self, cfg):
        self.gh = github.GitHub(cfg.github)
        self.tg = telegram.Telegram(cfg.telegram)
        self.repos = cfg.watcher.repositories
        self.poll_interval = cfg.watcher.poll_interval
        self.owner_id = cfg.console.allowed_user_id

    def _stream_prs(self, chat_id, header, prs, paths, line):
        self.tg.send(chat_id, header)

        found = processed = 0
        for pr in prs:
            processed += 1
            if processed % PROGRESS_EVERY == 0:
                self.tg.send(chat_id, f"processed {processed} PRs…")

            if not watcher.is_pr_watched(pr, paths):
                continue

            found += 1
            self.tg.send(chat_id, line(pr))

        if not found:
            self.tg.send(chat_id, "nothing found")

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
        if cmd == "/active":
            self.cmd_active(chat_id, parts[1] if len(parts) > 1 else "")
        elif cmd == "/closed":
            self.cmd_closed(chat_id, parts[1] if len(parts) > 1 else "")
        elif cmd in ("/start", "/help"):
            self.cmd_help(chat_id)
        else:
            self.cmd_unknown(chat_id)

    def cmd_active(self, chat_id, arg):
        days = _parse_days(arg)
        cutoff = now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — open PRs in watched paths created in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.active_prs(r.repo, cutoff), r.paths, active_pr_line)

    def cmd_closed(self, chat_id, arg):
        days = _parse_days(arg)
        cutoff = now() - datetime.timedelta(days=days)
        for r in self.repos:
            header = f"<b>{r.repo}</b> — PRs merged in watched paths in the last {days} day(s):"
            self._stream_prs(chat_id, header, self.gh.closed_prs(r.repo, cutoff), r.paths, closed_pr_line)

    def cmd_help(self, chat_id):
        lines = ["/active [days] — open PRs created in the last [days] days (default 1)",
                 "/closed [days] — PRs merged in the last [days] days (default 1)",
                 "/help — this message",
                 "",
                 f"poll interval: {self.poll_interval}s"]

        for r in self.repos:
            lines.append(f"{r.repo}:")
            lines += [f"  {p}" for p in r.paths]

        self.tg.send_lines(chat_id, lines)

    def cmd_unknown(self, chat_id):
        self.tg.send(chat_id, "Unknown command, try /help")
