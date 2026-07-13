import dataclasses
import logging
import time
from collections.abc import Iterable, Iterator
from typing import Any

import requests

from ..config import config
from . import retries

log = logging.getLogger("wardo.telegram")

MAX_LEN = 4096


@dataclasses.dataclass
class Message:
    user_id: int | None
    username: str | None
    chat_id: int
    text: str


def _parse_message(msg: dict[str, Any]) -> Message:
    user = msg.get("from", {})
    return Message(
        user_id=user.get("id"),
        username=user.get("username"),
        chat_id=msg["chat"]["id"],
        text=(msg.get("text") or "").strip(),
    )


def _chunk(lines: Iterable[str], limit: int = MAX_LEN) -> list[str]:
    parts, cur = [], ""
    for line in lines:
        if cur and len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = ""

        cur = f"{cur}\n{line}" if cur else line

    if cur:
        parts.append(cur)

    return parts


class Telegram:
    def __init__(self, cfg: config.TelegramConfig) -> None:
        self.api = f"https://api.telegram.org/bot{cfg.token}"

    def _send_message(self, chat_id: int, text: str) -> requests.Response:
        def call(s):
            return s.post(f"{self.api}/sendMessage", json={
                "chat_id": chat_id, "text": text,
                "parse_mode": "HTML", "disable_web_page_preview": True,
            }, timeout=30)

        return retries.request(call)

    def _get_updates(self, offset: int) -> list[dict[str, Any]]:
        def call(s):
            r = s.get(f"{self.api}/getUpdates", params={"offset": offset, "timeout": 50}, timeout=60)
            return r.json().get("result", [])

        return retries.request(call)

    def send(self, chat_id: int, text: str) -> None:
        r = self._send_message(chat_id, text)

        if not r.ok:
            log.error("sendMessage failed: %s", r.text)

    def send_lines(self, chat_id: int, lines: Iterable[str]) -> None:
        for part in _chunk(lines):
            self.send(chat_id, part)

    def updates(self) -> Iterator[Message]:
        offset = 0
        while True:
            try:
                results = self._get_updates(offset)
            except Exception:
                log.exception("getUpdates failed")
                time.sleep(5)
                continue

            for u in results:
                offset = u["update_id"] + 1
                if "message" in u:
                    yield _parse_message(u["message"])
