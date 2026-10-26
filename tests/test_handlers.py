from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from bot import handlers
from bot.config import settings
from bot.constants import *
from bot.state import BotState, read_order_state


class HandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = BotState()
        self.messages: list[tuple[tuple, dict]] = []
        self.send_patch = patch("bot.handlers.send_message", side_effect=lambda *args, **kwargs: self.messages.append((args, kwargs)) or {"message_id": 1})
        self.send_patch.start()
        self.addCleanup(self.send_patch.stop)
        self.request_patch = patch("bot.handlers.request", return_value={"message_id": 99})
        self.request = self.request_patch.start()
        self.addCleanup(self.request_patch.stop)

    def last_text(self) -> str:
        return self.messages[-1][0][1]

    def test_start_and_cancel_reset_expected_order_state(self) -> None:
        self.state.states[1] = "platform"
        self.state.delivery_preferences[1] = BUTTON_AIR_DELIVERY
        self.state.order_carts[1] = [{"price": "1"}]
        handlers.handle_text(1, "/start ignored", self.state)
        self.assertNotIn(1, self.state.states)
        self.assertNotIn(1, self.state.delivery_preferences)
        self.assertNotIn(1, self.state.order_carts)
        self.assertIn("Добро пожаловать", self.last_text())
        self.request.assert_not_called()

        self.state.states[1] = "question"
        handlers.handle_text(1, "/cancel", self.state)
        self.assertNotIn(1, self.state.states)
        self.assertIn("отменено", self.last_text())

    def test_main_navigation_and_other_menu_back(self) -> None:
        handlers.handle_text(1, BUTTON_OTHER_MENU, self.state)
        self.assertEqual(self.state.states[1], "other_menu")
        handlers.handle_text(1, BUTTON_BACK, self.state)
        self.assertNotIn(1, self.state.states)
        self.assertIn("меню", self.last_text())

    def test_question_and_tracking_submit_or_escape_text(self) -> None:
        self.state.states[1] = "question"
        with patch("bot.handlers.submit_question") as submit:
            handlers.handle_text(1, "When <delivery>?", self.state)
        submit.assert_called_once_with(self.state, 1, "When <delivery>?")
        self.assertNotIn(1, self.state.states)

        self.state.states[1] = "tracking"
        handlers.handle_text(1, "<TRACK>", self.state)
        self.assertIn("&lt;TRACK&gt;", self.last_text())

    def test_calculator_chinese_foreign_and_custom_currency_flows(self) -> None:
        handlers.handle_text(1, BUTTON_CALCULATOR, self.state)
        handlers.handle_text(1, "Poizon", self.state)
        self.assertEqual(self.state.states[1], "calculator_amount:CNY")
        handlers.handle_text(1, "100", self.state)
        self.assertNotIn(1, self.state.states)
        self.assertIn("54.45 ₽", self.last_text())

        handlers.handle_text(1, BUTTON_CALCULATOR, self.state)
        handlers.handle_text(1, "eBAY", self.state)
        handlers.handle_text(1, BUTTON_USD, self.state)
        handlers.handle_text(1, "19.9", self.state)
        self.assertIn("19.90 USD", self.last_text())

        self.state.states[1] = "calculator_custom_currency"
        handlers.handle_text(1, "btc", self.state)
        self.assertEqual(self.state.states[1], "calculator_amount:BTC")

    def test_calculator_rejects_invalid_platform_currency_and_amount(self) -> None:
        self.state.states[1] = "calculator_platform"
        handlers.handle_text(1, "unknown", self.state)
        self.assertEqual(self.state.states[1], "calculator_platform")
        self.assertIn("кнопкой", self.last_text())
        self.state.states[1] = "calculator_custom_currency"
        handlers.handle_text(1, "1$", self.state)
        self.assertIn("буквами", self.last_text())
        self.state.states[1] = "calculator_amount:CNY"
        handlers.handle_text(1, "0", self.state)
        self.assertEqual(self.state.states[1], "calculator_amount:CNY")
        self.assertIn("положительное", self.last_text())

    def test_begin_currency_selects_foreign_currency_or_chinese_category(self) -> None:
        handlers.begin_currency(self.state.states, 1, "Amazon")
        self.assertEqual(self.state.states[1], "currency:Amazon")
        handlers.begin_currency(self.state.states, 1, "Taobao")
        self.assertEqual(self.state.states[1], "category:Taobao|CNY")

    def test_full_chinese_order_flow_from_menu_to_confirmation(self) -> None:
        with patch("bot.handlers.product_photo_prompt") as photo_prompt, patch("bot.handlers.check_product_link", return_value=(True, "")):
            handlers.handle_text(1, BUTTON_ORDER, self.state)
            handlers.handle_text(1, "Poizon", self.state)
            handlers.handle_text(1, CATEGORY_BUTTONS[0], self.state)
            self.assertEqual(self.state.states[1], f"delivery:Poizon|CNY|{CATEGORY_BUTTONS[0]}")
            handlers.handle_text(1, BUTTON_AIR_DELIVERY, self.state)
            photo_prompt.assert_called_once_with(1)
            handlers.handle_photo(1, 22, self.state)
            handlers.handle_text(1, "https://example.test/item", self.state)
            handlers.handle_text(1, "2", self.state)
            handlers.handle_text(1, "42", self.state)
            handlers.handle_text(1, "12.50", self.state)

        data = read_order_state(self.state.states[1], "order_confirmation")
        self.assertEqual(data, {"platform": "Poizon", "currency": "CNY", "category": CATEGORY_BUTTONS[0], "delivery": BUTTON_AIR_DELIVERY, "link": "https://example.test/item", "photo_message_id": "22", "quantity": "2", "size": "42", "price": "12.50"})
        self.assertIn("13.61 ₽", self.last_text())

    def test_foreign_order_skips_delivery_and_custom_category_is_kept(self) -> None:
        with patch("bot.handlers.product_photo_prompt") as photo_prompt:
            handlers.handle_text(1, BUTTON_ORDER, self.state)
            handlers.handle_text(1, "Amazon", self.state)
            handlers.handle_text(1, BUTTON_EUR, self.state)
            handlers.handle_text(1, BUTTON_OTHER_CATEGORY, self.state)
            handlers.handle_text(1, "Vintage", self.state)

        self.assertEqual(self.state.states[1], "order_photo:Amazon|EUR|Vintage|Не указана")
        photo_prompt.assert_called_once_with(1)

    def test_invalid_link_quantity_and_price_keep_current_stage(self) -> None:
        self.state.states[1] = "order_link:Poizon|CNY|Shoes|Air"
        with patch("bot.handlers.check_product_link", return_value=(False, "bad link")):
            handlers.handle_text(1, "https://bad.test", self.state)
        self.assertEqual(self.state.states[1], "order_link:Poizon|CNY|Shoes|Air")
        self.assertIn("bad link", self.last_text())

        self.state.states[1] = 'order_quantity:{"currency": "CNY"}'
        handlers.handle_text(1, "0", self.state)
        self.assertIn("положительное", self.last_text())
        self.state.states[1] = 'order_price:{"currency": "CNY"}'
        handlers.handle_text(1, "-1", self.state)
        self.assertIn("положительную", self.last_text())

    def test_add_edit_and_confirm_order_actions(self) -> None:
        self.state.states[1] = 'order_confirmation:{"platform":"Poizon","currency":"CNY","category":"Shoes","delivery":"Air","link":"https://e.test","quantity":"1","size":"M","price":"10"}'
        handlers.handle_text(1, BUTTON_ADD_PRODUCT, self.state)
        self.assertEqual(len(self.state.order_carts[1]), 1)
        self.assertEqual(self.state.states[1], "platform")

        self.state.states[1] = 'order_confirmation:{"platform":"Poizon","currency":"CNY","category":"Shoes","delivery":"Air","link":"https://e.test","quantity":"1","size":"M","price":"10"}'
        handlers.handle_text(1, BUTTON_EDIT_ORDER, self.state)
        self.assertEqual(self.state.states[1], "platform")
        self.assertNotIn(1, self.state.order_carts)

        self.state.states[1] = 'order_confirmation:{"platform":"Poizon","currency":"CNY","category":"Shoes","delivery":"Air","link":"https://e.test","quantity":"1","size":"M","price":"10"}'
        with patch("bot.handlers.submit_order") as submit:
            handlers.handle_text(1, BUTTON_CONFIRM_ORDER, self.state)
        submit.assert_called_once()
        self.assertTrue(self.state.states[1].startswith("order_confirmed:"))
        self.assertIn("Общая стоимость", self.last_text())

    def test_order_summaries_calculate_each_currency_and_escape_values(self) -> None:
        cny = {"link": "https://e.test/?a=1&b=2", "quantity": "2", "size": "M<", "currency": "CNY", "price": "10"}
        usd = {"link": "https://u.test", "quantity": "1", "size": "L", "currency": "USD", "price": "7.5"}

        self.assertIn("10.89 ₽", handlers.order_summary_text([cny]))
        total = handlers.order_total_text([cny, usd])
        self.assertIn("20.00 CNY", total)
        self.assertIn("7.50 USD", total)
        self.assertIn("10.89 ₽", total)

    def test_photo_only_advances_from_expected_stage(self) -> None:
        handlers.handle_photo(1, 12, self.state)
        self.assertIn("после выбора", self.last_text())
        self.state.states[1] = "order_photo:Poizon|CNY|Shoes|Air"
        handlers.handle_photo(1, 12, self.state)
        self.assertEqual(self.state.order_photo_messages[1], 12)
        self.assertEqual(self.state.states[1], "order_link:Poizon|CNY|Shoes|Air")

    def test_handle_update_routes_forum_and_customer_messages(self) -> None:
        self.state.thread_users[70] = 1
        with patch("bot.handlers.relay_manager") as relay_manager:
            handlers.handle_update({"message": {"chat": {"id": -1003904305474}, "message_thread_id": 70, "message_id": 5, "from": {"username": "manager"}, "text": "hello"}}, self.state)
        relay_manager.assert_called_once()

        self.state.forum_threads[2] = 71
        with patch("bot.handlers.relay_customer") as relay_customer:
            handlers.handle_update({"message": {"chat": {"id": 2}, "message_id": 6, "from": {"first_name": "Buyer"}, "text": "hello"}}, self.state)
        relay_customer.assert_called_once()

    def test_handle_update_handles_document_image_and_manager_delete_command(self) -> None:
        with patch("bot.handlers.handle_photo") as photo:
            handlers.handle_update({"message": {"chat": {"id": 2}, "message_id": 6, "from": {}, "document": {"mime_type": "image/png"}}}, self.state)
        photo.assert_called_once_with(2, 6, self.state)

        self.state.thread_users[70] = 2
        manager_settings = replace(settings, manager_username="yeahhha31")
        with patch("bot.handlers.settings", manager_settings), patch("bot.handlers.delete_forum_message_and_copy") as delete:
            handlers.handle_update({"message": {"chat": {"id": -1003904305474}, "message_thread_id": 70, "message_id": 6, "reply_to_message": {"message_id": 5}, "from": {"username": "yeahhha31"}, "text": "/delete@bot"}}, self.state)
        delete.assert_called_once()
