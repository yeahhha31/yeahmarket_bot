from __future__ import annotations

from typing import Any

from .constants import *


def main_keyboard() -> dict[str, Any]:
    return {"keyboard": [[BUTTON_ORDER], [BUTTON_CALCULATOR], [BUTTON_FIND_BY_PHOTO], [BUTTON_QUESTION], [BUTTON_OTHER_MENU]], "resize_keyboard": True, "is_persistent": True, "input_field_placeholder": "Выберите действие"}


def other_keyboard() -> dict[str, Any]:
    return {"keyboard": [[BUTTON_FAQ], [BUTTON_TRACKING], [BUTTON_BARAHOLKA], [BUTTON_IOS], [BUTTON_ANDROID], [BUTTON_BACK]], "resize_keyboard": True, "is_persistent": True, "input_field_placeholder": "Выберите раздел"}


def platform_keyboard() -> dict[str, Any]:
    rows = [list(PLATFORM_BUTTONS[i:i + 2]) for i in range(0, len(PLATFORM_BUTTONS), 2)]
    return {"keyboard": [[BUTTON_FIND_BY_PHOTO]] + rows + [[BUTTON_BACK]], "resize_keyboard": True, "one_time_keyboard": True, "input_field_placeholder": "Выберите платформу"}


def currency_keyboard() -> dict[str, Any]:
    return {"keyboard": [[BUTTON_USD], [BUTTON_EUR], [BUTTON_BACK]], "resize_keyboard": True, "one_time_keyboard": True, "input_field_placeholder": "Выберите валюту"}


def delivery_keyboard() -> dict[str, Any]:
    return {"keyboard": [[BUTTON_AIR_DELIVERY], [BUTTON_AUTO_DELIVERY], [BUTTON_BACK]], "resize_keyboard": True, "one_time_keyboard": True, "input_field_placeholder": "Выберите способ доставки"}


def confirmation_keyboard() -> dict[str, Any]:
    return {"keyboard": [[BUTTON_EDIT_ORDER], [BUTTON_ADD_PRODUCT], [BUTTON_CONFIRM_ORDER]], "resize_keyboard": True, "one_time_keyboard": True, "input_field_placeholder": "Проверьте данные заказа"}
