from __future__ import annotations

import json

from .config import settings
from .state import BotState


def load(state: BotState) -> None:
    try:
        saved = json.loads(settings.forum_threads.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        saved = {}
    for customer_id, thread_id in saved.items():
        state.forum_threads[int(customer_id)] = int(thread_id)
        state.thread_users[int(thread_id)] = int(customer_id)
    try:
        links = json.loads(settings.message_links.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        links = {}
    for forum_message_id, link in links.items():
        if isinstance(link, dict) and "customer_chat_id" in link:
            state.message_links[int(forum_message_id)] = {
                "customer_chat_id": int(link["customer_chat_id"]),
                "customer_message_id": int(link["customer_message_id"]) if link.get("customer_message_id") is not None else None,
            }


def save(state: BotState) -> None:
    settings.forum_threads.write_text(json.dumps({str(k): v for k, v in state.forum_threads.items()}, ensure_ascii=False, indent=2), encoding="utf-8")


def save_message_links(state: BotState) -> None:
    settings.message_links.write_text(json.dumps({str(k): v for k, v in state.message_links.items()}, ensure_ascii=False, indent=2), encoding="utf-8")


def next_order_number() -> int:
    try:
        current = int(settings.order_counter.read_text(encoding="utf-8").strip() or "0")
    except (FileNotFoundError, ValueError):
        current = 0
    number = current + 1
    settings.order_counter.write_text(str(number), encoding="utf-8")
    return number
