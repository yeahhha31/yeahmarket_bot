from __future__ import annotations

from decimal import Decimal
from html import escape
from typing import Any

from .config import settings
from .persistence import next_order_number, save
from .state import BotState
from .telegram_api import request, send_message


def get_or_create_topic(state: BotState, chat_id: int, order_data: dict[str, str]) -> int:
    if chat_id in state.forum_threads:
        return state.forum_threads[chat_id]
    topic = request("createForumTopic", {"chat_id": settings.forum_chat_id, "name": f"Заявка {next_order_number()} | {order_data.get('platform', 'Общение')} | {order_data.get('category', 'Вопросы')}"[:128]})
    thread_id = topic["message_thread_id"]
    state.forum_threads[chat_id] = thread_id
    state.thread_users[thread_id] = chat_id
    save(state)
    return thread_id


def client_label(state: BotState, chat_id: int) -> str:
    profile = state.customer_profiles.get(chat_id, {})
    username = profile.get("username", "").strip().lstrip("@")
    if username:
        return f"@{escape(username)}"
    name = escape(" ".join(x for x in (profile.get("first_name", "Клиент"), profile.get("last_name", "")) if x) or "Клиент")
    return f'<a href="tg://user?id={chat_id}">{name}</a>'


def submit_order(state: BotState, chat_id: int, data: dict[str, str]) -> int:
    price = Decimal(data["price"])
    total = price * int(data["quantity"])
    link = escape(data["link"], quote=True)
    text = (
        "📩 <b>Новая заявка</b>\n\n"
        f"Клиент: <b>{client_label(state, chat_id)}</b>\n"
        f"Платформа: <b>{escape(data['platform'])}</b>\n"
        f"Валюта: <b>{escape(data['currency'])}</b>\n"
        f"Категория: <b>{escape(data['category'])}</b>\n"
        f"Доставка: <b>{escape(data['delivery'])}</b>\n"
        f"Ссылка: <a href=\"{link}\">{link}</a>\n"
        f"Количество: <b>{data['quantity']}</b>\nРазмер: <b>{escape(data['size'])}</b>\n"
        f"Стоимость: <b>{total} {escape(data['currency'])}</b>"
    )
    thread_id = get_or_create_topic(state, chat_id, data)
    send_message(settings.forum_chat_id, text, message_thread_id=thread_id)
    if data.get("photo_message_id"):
        request("copyMessage", {"chat_id": settings.forum_chat_id, "from_chat_id": chat_id, "message_id": int(data["photo_message_id"]), "message_thread_id": thread_id})
    return thread_id


def submit_question(state: BotState, chat_id: int, question: str) -> None:
    thread_id = get_or_create_topic(state, chat_id, {"platform": "Общение"})
    send_message(settings.forum_chat_id, f"❓ <b>Вопрос клиента</b>\n\n{escape(question)}", message_thread_id=thread_id)


def relay_customer(message: dict[str, Any], thread_id: int) -> None:
    request("copyMessage", {"chat_id": settings.forum_chat_id, "from_chat_id": message["chat"]["id"], "message_id": message["message_id"], "message_thread_id": thread_id})


def relay_manager(message: dict[str, Any], customer_chat_id: int) -> None:
    request("copyMessage", {"chat_id": customer_chat_id, "from_chat_id": message["chat"]["id"], "message_id": message["message_id"]})
