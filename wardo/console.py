import datetime
import html
import logging

from . import github, telegram

log = logging.getLogger("wardo.console")


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def link(pr):
    return f'<a href="{pr.url}">{html.escape(pr.title)}</a>'


def _unpack_request_msg(msg):
    user = msg.get("from", {})
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    return user.get("id"), user.get("username"), chat_id, text


def active_lines(repo, prs):
    if not prs:
        return [f"<b>{repo}</b> — no open PRs in watched paths"]

    lines = [f"<b>{repo}</b> — {len(prs)} open PR(s) in watched paths"]
    for pr in prs:
        sub = "🔔 subscribed" if pr.subscribed else "🔕 not subscribed"
        lines.append(f"• {link(pr)} — {pr.author} — {sub}")

    return lines


def closed_lines(repo, prs, days):
    if not prs:
        return [f"<b>{repo}</b> — nothing merged in watched paths in the last {days} day(s)"]

    lines = [f"<b>{repo}</b> — merged in watched paths in the last {days} day(s)"]
    lines += [f"• {link(pr)} — {pr.author}" for pr in prs]

    return lines


class Console:
    def __init__(self, cfg):
        self.gh = github.GitHub(cfg.github)
        self.tg = telegram.Telegram(cfg.telegram)
        self.repos = cfg.watcher.repositories
        self.poll_interval = cfg.watcher.poll_interval
        self.owner_id = cfg.console.allowed_user_id

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
            self.cmd_active(chat_id)
        elif cmd == "/closed":
            self.cmd_closed(chat_id, parts[1] if len(parts) > 1 else "")
        elif cmd in ("/start", "/help"):
            self.cmd_help(chat_id)
        else:
            self.cmd_unknown(chat_id)

    def cmd_active(self, chat_id):
        for r in self.repos:
            prs = self.gh.active_prs(r.repo, r.paths)
            self.tg.send_lines(chat_id, active_lines(r.repo, prs))

    def cmd_closed(self, chat_id, arg):
        try:
            days = int(arg)
            if days <= 0:
                raise ValueError
        except ValueError:
            self.tg.send(chat_id, "usage: /closed <days>")
            return

        cutoff = now() - datetime.timedelta(days=days)
        for r in self.repos:
            prs = self.gh.closed_prs(r.repo, r.paths, cutoff)
            self.tg.send_lines(chat_id, closed_lines(r.repo, prs, days))

    def cmd_help(self, chat_id):
        lines = ["wardo — GitHub PR path monitor",
                 "/active — open PRs touching watched paths",
                 "/closed <days> — PRs merged in the last <days> days",
                 "/help — this message",
                 "",
                 f"poll interval: {self.poll_interval}s"]

        for r in self.repos:
            lines.append(f"{r.repo}:")
            lines += [f"  {p}" for p in r.paths]

        self.tg.send_lines(chat_id, lines)

    def cmd_unknown(self, chat_id):
        self.tg.send(chat_id, "Unknown command, try /help")
