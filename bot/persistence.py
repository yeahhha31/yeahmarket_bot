from __future__ import annotations

import json

from .config import settings
from .state import BotState


def load(state: BotState) -> None:
    try:
        saved = json.loads(settings.forum_threads.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return
    for customer_id, thread_id in saved.items():
        state.forum_threads[int(customer_id)] = int(thread_id)
        state.thread_users[int(thread_id)] = int(customer_id)


def save(state: BotState) -> None:
    settings.forum_threads.write_text(json.dumps({str(k): v for k, v in state.forum_threads.items()}, ensure_ascii=False, indent=2), encoding="utf-8")


def next_order_number() -> int:
    try:
        current = int(settings.order_counter.read_text(encoding="utf-8").strip() or "0")
    except (FileNotFoundError, ValueError):
        current = 0
    number = current + 1
    settings.order_counter.write_text(str(number), encoding="utf-8")
    return number
