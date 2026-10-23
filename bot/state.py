from __future__ import annotations

import json


def make_order_state(stage: str, data: dict[str, str]) -> str:
    return f"{stage}:{json.dumps(data, ensure_ascii=False)}"


def read_order_state(state: str, stage: str) -> dict[str, str]:
    if not state.startswith(f"{stage}:"):
        raise ValueError(f"Unexpected order state: {state}")
    return json.loads(state.split(":", 1)[1])


class BotState:
    def __init__(self) -> None:
        self.states: dict[int, str] = {}
        self.order_photo_messages: dict[int, int] = {}
        self.customer_profiles: dict[int, dict[str, str]] = {}
        self.forum_threads: dict[int, int] = {}
        self.thread_users: dict[int, int] = {}
