from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from html import escape
from typing import Any

from .config import settings
from .persistence import next_order_number, save, save_message_links
from .state import BotState
from .telegram_api import request, send_message


def round_money_up(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_CEILING)


def get_or_create_topic(state: BotState, chat_id: int, order_data: dict[str, str]) -> int:
    if chat_id in state.forum_threads:
        return state.forum_threads[chat_id]
    topic = request("createForumTopic", {"chat_id": settings.forum_chat_id, "name": f"Заявка {next_order_number()} | {order_data.get('platform', 'Общение')}"[:128]})
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


def _link_message(state: BotState, forum_message_id: int, customer_chat_id: int, customer_message_id: int | None = None) -> None:
    state.message_links[forum_message_id] = {
        "customer_chat_id": customer_chat_id,
        "customer_message_id": customer_message_id,
    }
    save_message_links(state)


def submit_order(state: BotState, chat_id: int, items: list[dict[str, str]]) -> int:
    lines = ["📩 <b>Новая заявка</b>", "", f"Клиент: <b>{client_label(state, chat_id)}</b>", ""]
    for number, data in enumerate(items, 1):
        price = Decimal(data["price"])
        total = price * int(data["quantity"])
        link = escape(data["link"], quote=True)
        lines.extend([
            f"<b>Товар {number}</b>",
            f"Платформа: <b>{escape(data['platform'])}</b>",
            f"Валюта: <b>{escape(data['currency'])}</b>",
            f"Доставка: <b>{escape(data['delivery'])}</b>",
            f"Ссылка: <a href=\"{link}\">{link}</a>",
            f"Количество: <b>{data['quantity']}</b>",
            f"Размер: <b>{escape(data['size'])}</b>",
            f"Стоимость: <b>{total} {escape(data['currency'])}</b>",
        ])
        if data["currency"] == "CNY":
            rubles = round_money_up(total * Decimal("0.495") * Decimal("1.10"))
            lines.append(f"Стоимость в рублях: <b>{rubles} ₽</b>")
        lines.append("")
    text = "\n".join(lines).rstrip()
    thread_id = get_or_create_topic(state, chat_id, items[0])
    forum_text = send_message(settings.forum_chat_id, text, message_thread_id=thread_id)
    _link_message(state, forum_text["message_id"], chat_id)
    for data in items:
        if data.get("photo_message_id"):
            forum_photo = request("copyMessage", {"chat_id": settings.forum_chat_id, "from_chat_id": chat_id, "message_id": int(data["photo_message_id"]), "message_thread_id": thread_id})
            _link_message(state, forum_photo["message_id"], chat_id, int(data["photo_message_id"]))
    return thread_id


def submit_question(state: BotState, chat_id: int, question: str) -> None:
    thread_id = get_or_create_topic(state, chat_id, {"platform": "Общение"})
    send_message(settings.forum_chat_id, f"❓ <b>Вопрос клиента</b>\n\n{escape(question)}", message_thread_id=thread_id)


def submit_photo_search(state: BotState, chat_id: int, message_id: int) -> None:
    thread_id = get_or_create_topic(state, chat_id, {"platform": "Поиск по фото"})
    copied = request("copyMessage", {
        "chat_id": settings.forum_chat_id,
        "from_chat_id": chat_id,
        "message_id": message_id,
        "message_thread_id": thread_id,
    })
    _link_message(state, copied["message_id"], chat_id, message_id)
    send_message(settings.forum_chat_id, "🔎 Клиент хочет найти товар по фото.", message_thread_id=thread_id)


def relay_customer(message: dict[str, Any], thread_id: int, state: BotState) -> None:
    copied = request("copyMessage", {"chat_id": settings.forum_chat_id, "from_chat_id": message["chat"]["id"], "message_id": message["message_id"], "message_thread_id": thread_id})
    _link_message(state, copied["message_id"], int(message["chat"]["id"]), int(message["message_id"]))


def relay_manager(message: dict[str, Any], customer_chat_id: int, state: BotState) -> None:
    copied = request("copyMessage", {"chat_id": customer_chat_id, "from_chat_id": message["chat"]["id"], "message_id": message["message_id"]})
    _link_message(state, int(message["message_id"]), customer_chat_id, int(copied["message_id"]))


def delete_forum_message_and_copy(state: BotState, message: dict[str, Any]) -> None:
    target = message.get("reply_to_message") or {}
    target_id = target.get("message_id")
    if target_id is None:
        return
    link = state.message_links.pop(int(target_id), None)
    request("deleteMessage", {"chat_id": settings.forum_chat_id, "message_id": int(target_id)})
    if link and link.get("customer_message_id") is not None:
        try:
            request("deleteMessage", {"chat_id": link["customer_chat_id"], "message_id": link["customer_message_id"]})
        except (RuntimeError, ValueError):
            # The customer may have deleted their own message already.
            pass
    try:
        request("deleteMessage", {"chat_id": settings.forum_chat_id, "message_id": int(message["message_id"])})
    except (RuntimeError, ValueError):
        pass
    save_message_links(state)
