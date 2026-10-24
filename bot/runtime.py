from __future__ import annotations

import json
import time
import urllib.error

from .config import log, settings
from .handlers import handle_update
from .persistence import load
from .state import BotState
from .telegram_api import request


def run() -> None:
    if not settings.token:
        raise SystemExit("Set BOT_TOKEN before starting the bot")
    state = BotState()
    load(state)
    log.info("Starting yeahmarket_bot")
    offset = 0
    commands_configured = False
    while True:
        try:
            if not commands_configured:
                request("setMyCommands", {"commands": [{"command": "start", "description": "Открыть меню"}, {"command": "cancel", "description": "Отменить действие"}]})
                commands_configured = True
            updates = request("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message"]})
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    handle_update(update, state)
                except (urllib.error.URLError, RuntimeError, ValueError, KeyError, json.JSONDecodeError):
                    log.exception("Could not process update %s", update.get("update_id"))
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError):
            commands_configured = False
            log.exception("Polling failed; retrying in 5 seconds")
            time.sleep(5)
