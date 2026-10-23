from __future__ import annotations

import json
import time
import urllib.error
from decimal import Decimal, InvalidOperation
from html import escape
from typing import Any

from .config import log, settings
from .constants import *
from .forum import client_label, relay_customer, relay_manager, submit_order, submit_question
from .keyboards import *
from .state import BotState, make_order_state, read_order_state
from .telegram_api import request, send_local_photo, send_message
from .validation import check_product_link


def welcome(chat_id: int) -> None:
    send_message(chat_id, WELCOME_TEXT, reply_markup=main_keyboard())


def product_photo_prompt(chat_id: int) -> None:
    waiting = request("sendMessage", {"chat_id": chat_id, "text": "⏳ Подождите, формируется сообщение..."})
    try:
        caption = "🖼 <b>Пожалуйста, вставьте фото товара, как показано на примере вне зависимости от платформы:</b>"
        if settings.example_product_image.exists():
            send_local_photo(chat_id, settings.example_product_image, caption, remove_keyboard=True)
        else:
            send_message(chat_id, caption, remove_keyboard=True)
    finally:
        try:
            request("deleteMessage", {"chat_id": chat_id, "message_id": waiting["message_id"]})
        except (urllib.error.URLError, RuntimeError, ValueError):
            log.warning("Could not delete waiting message")


def begin_currency(states: dict[int, str], chat_id: int, platform: str) -> None:
    if platform in FOREIGN_PLATFORMS:
        states[chat_id] = f"currency:{platform}"
        send_message(chat_id, f"Платформа <b>{platform}</b> выбрана. Укажите валюту товара:", reply_markup=currency_keyboard())
    else:
        states[chat_id] = f"category:{platform}|CNY"
        send_message(chat_id, f"Платформа <b>{platform}</b> выбрана. Цена указывается в юанях (CNY). Выберите категорию товара:", reply_markup=category_keyboard())


def handle_text(chat_id: int, text: str, state: BotState) -> None:
    text = text.strip()
    current = state.states.get(chat_id, "")
    if text.startswith("/start") or text == "/menu":
        state.states.pop(chat_id, None)
        welcome(chat_id)
        return
    if text in {"/cancel", "Отмена"}:
        state.states.pop(chat_id, None)
        send_message(chat_id, "Действие отменено. Выберите нужный раздел в меню.", reply_markup=main_keyboard())
        return
    if text == BUTTON_OTHER_MENU:
        state.states[chat_id] = "other_menu"
        send_message(chat_id, "Выберите нужный раздел:", reply_markup=other_keyboard())
        return
    if current == "other_menu" and text == BUTTON_BACK:
        state.states.pop(chat_id, None)
        send_message(chat_id, "Выберите нужный раздел в меню.", reply_markup=main_keyboard())
        return

    if current == "question":
        try:
            submit_question(state, chat_id, text)
            state.states.pop(chat_id, None)
            send_message(chat_id, "✅ Вопрос отправлен менеджеру. Ответ придёт сюда.", reply_markup=main_keyboard())
        except (urllib.error.URLError, RuntimeError, ValueError):
            log.exception("Could not send question")
            send_message(chat_id, "Ошибка. Попробуйте позже.")
        return
    if current == "tracking":
        state.states.pop(chat_id, None)
        send_message(chat_id, f"Номер <b>{escape(text)}</b> записан. Проверить статус можно у перевозчика или менеджера.", reply_markup=main_keyboard())
        return
    if current == "calculator_platform":
        if text == BUTTON_BACK:
            state.states.pop(chat_id, None); send_message(chat_id, "Выберите нужный раздел.", reply_markup=main_keyboard()); return
        if text == BUTTON_CUSTOM_PLATFORM:
            state.states[chat_id] = "calculator_custom_currency"
            send_message(chat_id, "Напишите валюту для расчёта, например: <b>USD</b>, <b>EUR</b> или <b>CNY</b>."); return
        if text not in PLATFORM_BUTTONS:
            send_message(chat_id, "Выберите площадку кнопкой ниже.", reply_markup=platform_keyboard()); return
        if text in FOREIGN_PLATFORMS:
            state.states[chat_id] = f"calculator_currency:{text}"
            send_message(chat_id, f"Площадка <b>{text}</b> выбрана. Выберите валюту:", reply_markup=currency_keyboard()); return
        state.states[chat_id] = "calculator_amount:CNY"
        send_message(chat_id, "Цена на китайской площадке указывается в юанях (CNY). Введите сумму товара."); return
    if current.startswith("calculator_currency:"):
        if text == BUTTON_BACK:
            state.states[chat_id] = "calculator_platform"; send_message(chat_id, "Выберите площадку:", reply_markup=platform_keyboard()); return
        currency = "USD" if text == BUTTON_USD else "EUR" if text == BUTTON_EUR else ""
        if not currency:
            send_message(chat_id, "Выберите валюту кнопкой ниже.", reply_markup=currency_keyboard()); return
        state.states[chat_id] = f"calculator_amount:{currency}"
        send_message(chat_id, f"Введите сумму товара в валюте <b>{currency}</b>."); return
    if current == "calculator_custom_currency":
        currency = text.upper()
        if not currency.isalpha() or len(currency) > 10:
            send_message(chat_id, "Напишите валюту буквами, например: <b>USD</b> или <b>CNY</b>."); return
        state.states[chat_id] = f"calculator_amount:{currency}"; send_message(chat_id, f"Введите сумму товара в валюте <b>{currency}</b>."); return
    if current.startswith("calculator_amount:"):
        currency = current.split(":", 1)[1]
        try:
            amount = Decimal(text.replace(",", ".").replace("₽", ""))
            if amount <= 0: raise InvalidOperation
        except InvalidOperation:
            send_message(chat_id, f"Введите положительное число в валюте <b>{currency}</b>, например: <b>299</b>."); return
        state.states.pop(chat_id, None)
        if currency == "CNY":
            total = amount * Decimal("0.485") * Decimal("1.08")
            result = f"Ориентировочная стоимость: <b>{total.quantize(Decimal('0.01'))} ₽</b>.\nРасчёт: цена в CNY × 0.485 + 8%."
        else:
            result = f"Стоимость товара: <b>{amount.quantize(Decimal('0.01'))} {currency}</b>."
        send_message(chat_id, result, reply_markup=main_keyboard()); return

    if current == "platform":
        if text == BUTTON_BACK:
            state.states.pop(chat_id, None); send_message(chat_id, "Выберите нужный раздел.", reply_markup=main_keyboard()); return
        if text == BUTTON_CUSTOM_PLATFORM:
            state.states[chat_id] = "custom_platform"; send_message(chat_id, "Напишите название площадки."); return
        if text in PLATFORM_BUTTONS: begin_currency(state.states, chat_id, text)
        else: send_message(chat_id, "Выберите платформу кнопкой ниже.", reply_markup=platform_keyboard())
        return
    if current == "custom_platform":
        state.states[chat_id] = f"currency:{text}"; send_message(chat_id, "Напишите валюту, в которой будет производиться выкуп товара, например: <b>USD</b>, <b>EUR</b> или <b>CNY</b>."); return
    if current.startswith("currency:"):
        platform = current.split(":", 1)[1]
        if text == BUTTON_BACK:
            state.states[chat_id] = "platform"; send_message(chat_id, "Выберите платформу:", reply_markup=platform_keyboard()); return
        if platform in FOREIGN_PLATFORMS:
            currency = "USD" if text == BUTTON_USD else "EUR" if text == BUTTON_EUR else ""
            if not currency: send_message(chat_id, "Выберите валюту кнопкой ниже.", reply_markup=currency_keyboard()); return
        else:
            currency = text.upper()
            if not currency.isalpha() or len(currency) > 10: send_message(chat_id, "Напишите валюту буквами, например: <b>CNY</b>."); return
        state.states[chat_id] = f"category:{platform}|{currency}"; send_message(chat_id, "Выберите категорию товара:", reply_markup=category_keyboard()); return
    if current.startswith("category:"):
        platform, currency = current.split(":", 1)[1].split("|", 1)
        if text == BUTTON_BACK:
            state.states[chat_id] = f"currency:{platform}"; send_message(chat_id, "Выберите валюту:", reply_markup=currency_keyboard() if platform in FOREIGN_PLATFORMS else category_keyboard()); return
        if text in CATEGORY_BUTTONS:
            state.states[chat_id] = f"delivery:{platform}|{currency}|{text}"; send_message(chat_id, "📦 <b>Укажите способ доставки:</b>\n\n✈️ Авиа — 3–10 дней\n🚚 Авто — ~20 дней", reply_markup=delivery_keyboard()); return
        if text == BUTTON_OTHER_CATEGORY:
            state.states[chat_id] = f"custom_category:{platform}|{currency}"; send_message(chat_id, "Введите категорию товара своими словами."); return
        send_message(chat_id, "Выберите категорию кнопкой ниже.", reply_markup=category_keyboard()); return
    if current.startswith("custom_category:"):
        platform, currency = current.split(":", 1)[1].split("|", 1); state.states[chat_id] = f"delivery:{platform}|{currency}|{text}"; send_message(chat_id, "📦 <b>Укажите способ доставки:</b>", reply_markup=delivery_keyboard()); return
    if current.startswith("delivery:"):
        platform, currency, category = current.split(":", 1)[1].split("|", 2)
        if text == BUTTON_BACK: state.states[chat_id] = f"category:{platform}|{currency}"; send_message(chat_id, "Выберите категорию:", reply_markup=category_keyboard()); return
        if text in {BUTTON_AIR_DELIVERY, BUTTON_AUTO_DELIVERY}: state.states[chat_id] = f"order_photo:{platform}|{currency}|{category}|{text}"; product_photo_prompt(chat_id); return
        send_message(chat_id, "Выберите способ доставки кнопкой ниже.", reply_markup=delivery_keyboard()); return
    if current.startswith("order_link:"):
        parts = current.split(":", 1)[1].split("|", 3)
        if len(parts) == 3: platform, category, delivery = parts; currency = "CNY"
        elif len(parts) == 4: platform, currency, category, delivery = parts
        else: state.states.pop(chat_id, None); send_message(chat_id, "Ошибка. Попробуйте начать оформление заново."); return
        send_message(chat_id, "⏳ Проверяю ссылку на товар...")
        valid, error = check_product_link(text)
        if not valid: send_message(chat_id, f"❌ {error}\n\nОтправьте рабочую ссылку ещё раз."); return
        data = {"platform": platform, "currency": currency, "category": category, "delivery": delivery, "link": text}
        if chat_id in state.order_photo_messages: data["photo_message_id"] = str(state.order_photo_messages[chat_id])
        state.states[chat_id] = make_order_state("order_quantity", data); send_message(chat_id, "Ссылка получена. Укажите количество товара целым числом."); return
    if current.startswith("order_quantity:"):
        try: quantity = int(text); assert quantity > 0
        except (ValueError, AssertionError): send_message(chat_id, "Введите положительное количество целым числом."); return
        data = read_order_state(current, "order_quantity"); data["quantity"] = str(quantity); state.states[chat_id] = make_order_state("order_size", data); send_message(chat_id, "Укажите размер товара или другой вариант."); return
    if current.startswith("order_size:"):
        data = read_order_state(current, "order_size"); data["size"] = text; state.states[chat_id] = make_order_state("order_price", data); send_message(chat_id, f"Укажите цену товара в валюте <b>{data['currency']}</b>."); return
    if current.startswith("order_price:"):
        try: price = Decimal(text.replace(",", ".").replace("¥", "").replace("￥", "")); assert price > 0
        except (InvalidOperation, AssertionError): send_message(chat_id, "Введите положительную цену."); return
        data = read_order_state(current, "order_price"); data["price"] = str(price); state.states[chat_id] = make_order_state("order_confirmation", data)
        link = escape(data["link"], quote=True)
        send_message(chat_id, f"<b>Ссылка на товар:</b> <a href=\"{link}\">{link}</a>\n<b>Количество товара:</b> {data['quantity']}\n<b>Размер товара:</b> {escape(data['size'])}\n<b>Стоимость в {escape(data['currency'])}:</b> {price}\n\n⚠️ Если Вы по ошибке оплатили неверную сумму и хотите вернуть свои деньги обратно, заявка на возврат средств обрабатывается в течение <b>7 рабочих дней</b>. Будьте внимательны!")
        send_message(chat_id, "Проверьте данные заявки:", reply_markup=confirmation_keyboard()); return
    if current.startswith("order_confirmation:"):
        data = read_order_state(current, "order_confirmation")
        if text == BUTTON_EDIT_ORDER: state.states[chat_id] = "platform"; send_message(chat_id, "Начнём оформление заново. Выберите платформу:", reply_markup=platform_keyboard()); return
        if text == BUTTON_ADD_PRODUCT: state.states[chat_id] = "platform"; send_message(chat_id, "Добавим новый товар. Выберите платформу:", reply_markup=platform_keyboard()); return
        if text == BUTTON_CONFIRM_ORDER:
            try: submit_order(state, chat_id, data); state.states[chat_id] = make_order_state("order_confirmed", data); send_message(chat_id, "✅ Заявка отправлена менеджеру.", reply_markup=main_keyboard())
            except (urllib.error.URLError, RuntimeError, ValueError): log.exception("Could not submit order"); send_message(chat_id, "Ошибка. Попробуйте позже.", reply_markup=confirmation_keyboard())
            return
        send_message(chat_id, "Выберите «📝 Изменить» или «✅ Верно».", reply_markup=confirmation_keyboard()); return

    if text == BUTTON_ORDER: state.states[chat_id] = "platform"; send_message(chat_id, "Выберите платформу:", reply_markup=platform_keyboard())
    elif text == BUTTON_CALCULATOR: state.states[chat_id] = "calculator_platform"; send_message(chat_id, "Выберите площадку для расчёта:", reply_markup=platform_keyboard())
    elif text == BUTTON_QUESTION: state.states[chat_id] = "question"; send_message(chat_id, "Напишите свой вопрос одним сообщением.")
    elif text == BUTTON_FAQ: send_message(chat_id, "<b>Частые вопросы</b>\n\n• Срок выкупа: обычно 1–2 рабочих дня.\n• Доставка: рассчитывается отдельно по весу и направлению.\n• Оплата: только внутри этого бота.\n• Для расчёта отправьте ссылку на товар менеджеру.")
    elif text == BUTTON_TRACKING: state.states[chat_id] = "tracking"; send_message(chat_id, "Отправьте трек-номер посылки.")
    elif text == BUTTON_BARAHOLKA: send_message(chat_id, f"Барахолка: <a href=\"{settings.baraholka_url}\">открыть раздел</a>" if settings.baraholka_url else "Раздел пока настраивается.")
    elif text == BUTTON_IOS: send_message(chat_id, f"<a href=\"{settings.ios_url}\">Открыть App Store</a>" if settings.ios_url else "Ссылка пока настраивается.")
    elif text == BUTTON_ANDROID: send_message(chat_id, f"<a href=\"{settings.android_url}\">Открыть Google Play</a>" if settings.android_url else "Ссылка пока настраивается.")
    else: send_message(chat_id, "Выберите действие в меню.", reply_markup=main_keyboard())


def handle_photo(chat_id: int, message_id: int, state: BotState) -> None:
    current = state.states.get(chat_id, "")
    if not current.startswith("order_photo:"):
        send_message(chat_id, "Отправьте фото после выбора доставки.", reply_markup=main_keyboard()); return
    state.order_photo_messages[chat_id] = message_id
    state.states[chat_id] = f"order_link:{current.split(':', 1)[1]}"
    send_message(chat_id, "🔗 <b>Пожалуйста, отправьте ссылку на товар в нужном формате. Пример: https://dw4.co/t/A/HnCbd4E8B</b>")


def handle_update(update: dict[str, Any], state: BotState) -> None:
    message = update.get("message")
    if not message or not message.get("chat"): return
    chat_id = message["chat"]["id"]; sender = message.get("from") or {}
    state.customer_profiles[chat_id] = {"username": sender.get("username", ""), "first_name": sender.get("first_name", "Клиент"), "last_name": sender.get("last_name", "")}
    if str(chat_id) == settings.forum_chat_id:
        customer = state.thread_users.get(message.get("message_thread_id"))
        if customer is not None and not sender.get("is_bot"): relay_manager(message, customer)
        return
    if chat_id in state.forum_threads and not sender.get("is_bot") and message.get("text"):
        current = state.states.get(chat_id, "")
        menu_actions = {
            BUTTON_ORDER, BUTTON_CALCULATOR, BUTTON_QUESTION, BUTTON_OTHER_MENU,
            BUTTON_FAQ, BUTTON_TRACKING, BUTTON_BARAHOLKA, BUTTON_IOS, BUTTON_ANDROID,
            BUTTON_BACK, BUTTON_CUSTOM_PLATFORM, BUTTON_OTHER_CATEGORY,
            BUTTON_AIR_DELIVERY, BUTTON_AUTO_DELIVERY, BUTTON_EDIT_ORDER,
            BUTTON_ADD_PRODUCT, BUTTON_CONFIRM_ORDER, BUTTON_USD, BUTTON_EUR, *PLATFORM_BUTTONS, *CATEGORY_BUTTONS,
        }
        if (not current or current.startswith("order_confirmed:")) and not message["text"].startswith("/") and message["text"] not in menu_actions:
            relay_customer(message, state.forum_threads[chat_id]); return
    if message.get("photo"): handle_photo(chat_id, message["message_id"], state)
    elif message.get("document") and ((message["document"].get("mime_type") or "").startswith("image/") or (message["document"].get("file_name") or "").lower().endswith((".jpg", ".jpeg", ".png", ".webp"))): handle_photo(chat_id, message["message_id"], state)
    elif message.get("text"): handle_text(chat_id, message["text"], state)
