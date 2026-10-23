from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import settings


def request(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.token:
        raise RuntimeError("BOT_TOKEN is not set")
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{settings.api_url}/{method}", data=data, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code} in {method}: {details}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error in {method}: {result}")
    return result["result"]


def send_message(chat_id: int | str, text: str, *, reply_markup: dict[str, Any] | None = None, remove_keyboard: bool = False, message_thread_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    elif remove_keyboard:
        payload["reply_markup"] = {"remove_keyboard": True}
    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id
    return request("sendMessage", payload)


def send_local_photo(chat_id: int | str, path: Path, caption: str, *, reply_markup: dict[str, Any] | None = None, remove_keyboard: bool = False) -> dict[str, Any]:
    fields = {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"}
    if reply_markup is not None:
        fields["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    elif remove_keyboard:
        fields["reply_markup"] = json.dumps({"remove_keyboard": True})
    boundary = f"----ChinaFairyTale{int(time.time() * 1000)}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{path.name}\"\r\nContent-Type: image/png\r\n\r\n".encode())
    body.extend(path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"{settings.api_url}/sendPhoto", data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    with urllib.request.urlopen(req, timeout=40) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error in sendPhoto: {result}")
    return result["result"]
