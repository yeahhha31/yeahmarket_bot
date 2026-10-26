from __future__ import annotations

import json

from .config import settings
from .state import BotState


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load(state: BotState) -> None:
    try:
        saved = json.loads(settings.forum_threads.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    for customer_id, thread_id in saved.items():
        try:
            customer = int(customer_id)
            thread = int(thread_id)
        except (TypeError, ValueError):
            continue
        state.forum_threads[customer] = thread
        state.thread_users[thread] = customer
    try:
        links = json.loads(settings.message_links.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        links = {}
    if not isinstance(links, dict):
        links = {}
    for forum_message_id, link in links.items():
        if isinstance(link, dict) and "customer_chat_id" in link:
            try:
                state.message_links[int(forum_message_id)] = {
                    "customer_chat_id": int(link["customer_chat_id"]),
                    "customer_message_id": int(link["customer_message_id"]) if link.get("customer_message_id") is not None else None,
                }
            except (TypeError, ValueError):
                continue


def save(state: BotState) -> None:
    _write(settings.forum_threads, json.dumps({str(k): v for k, v in state.forum_threads.items()}, ensure_ascii=False, indent=2))


def save_message_links(state: BotState) -> None:
    _write(settings.message_links, json.dumps({str(k): v for k, v in state.message_links.items()}, ensure_ascii=False, indent=2))


def next_order_number() -> int:
    try:
        current = int(settings.order_counter.read_text(encoding="utf-8").strip() or "0")
    except (FileNotFoundError, ValueError):
        current = 0
    number = current + 1
    _write(settings.order_counter, str(number))
    return number
