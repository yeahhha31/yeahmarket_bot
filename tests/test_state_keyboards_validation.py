from __future__ import annotations

import urllib.error
import unittest
from unittest.mock import MagicMock, patch

from bot import constants
from bot.keyboards import (
    confirmation_keyboard,
    currency_keyboard,
    delivery_keyboard,
    main_keyboard,
    other_keyboard,
    platform_keyboard,
)
from bot.state import BotState, make_order_state, read_order_state
from bot.validation import check_product_link


class StateTests(unittest.TestCase):
    def test_order_state_round_trip_preserves_unicode_and_colons(self) -> None:
        data = {"platform": "Рыбка", "link": "https://example.test/a:b", "quantity": "2"}

        state = make_order_state("order_quantity", data)

        self.assertEqual(read_order_state(state, "order_quantity"), data)

    def test_read_order_state_rejects_another_stage(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unexpected order state"):
            read_order_state("order_size:{}", "order_quantity")

    def test_bot_state_starts_with_independent_empty_collections(self) -> None:
        first = BotState()
        second = BotState()
        first.states[1] = "platform"

        self.assertEqual(second.states, {})
        self.assertEqual(first.order_carts, {})
        self.assertEqual(first.message_links, {})


class KeyboardTests(unittest.TestCase):
    def test_main_and_other_keyboards_have_expected_navigation(self) -> None:
        main = main_keyboard()
        other = other_keyboard()

        self.assertEqual(main["keyboard"], [[constants.BUTTON_ORDER], [constants.BUTTON_CALCULATOR], [constants.BUTTON_FIND_BY_PHOTO], [constants.BUTTON_QUESTION], [constants.BUTTON_OTHER_MENU]])
        self.assertTrue(main["is_persistent"])
        self.assertIn([constants.BUTTON_BACK], other["keyboard"])

    def test_platform_keyboard_contains_every_platform_in_two_column_rows(self) -> None:
        keyboard = platform_keyboard()
        self.assertEqual(keyboard["keyboard"][0], [constants.BUTTON_FIND_BY_PHOTO])
        choices = [item for row in keyboard["keyboard"][1:-1] for item in row]

        self.assertEqual(choices, list(constants.PLATFORM_BUTTONS))
        self.assertTrue(all(len(row) <= 2 for row in keyboard["keyboard"][1:-1]))
        self.assertEqual(keyboard["keyboard"][-1], [constants.BUTTON_BACK])

    def test_currency_delivery_and_confirmation_keyboards_have_all_actions(self) -> None:
        self.assertEqual(currency_keyboard()["keyboard"], [[constants.BUTTON_USD], [constants.BUTTON_EUR], [constants.BUTTON_BACK]])
        self.assertEqual(delivery_keyboard()["keyboard"], [[constants.BUTTON_AIR_DELIVERY], [constants.BUTTON_AUTO_DELIVERY], [constants.BUTTON_BACK]])
        self.assertEqual(confirmation_keyboard()["keyboard"], [[constants.BUTTON_EDIT_ORDER], [constants.BUTTON_ADD_PRODUCT], [constants.BUTTON_CONFIRM_ORDER]])


class ProductLinkValidationTests(unittest.TestCase):
    def test_invalid_link_shapes_do_not_attempt_network_access(self) -> None:
        for link in ("example.com/item", "ftp://example.com", "https:///item", "https://example.com/a b"):
            with self.subTest(link=link), patch("bot.validation.urllib.request.urlopen") as urlopen:
                self.assertEqual(check_product_link(link)[0], False)
                urlopen.assert_not_called()

    def test_successful_head_response_is_accepted(self) -> None:
        response = MagicMock(status=200)
        with patch("bot.validation.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = response

            self.assertEqual(check_product_link(" https://example.com/product "), (True, ""))
            request = urlopen.call_args.args[0]

        self.assertEqual(request.get_method(), "HEAD")
        self.assertEqual(request.headers["User-agent"], "Mozilla/5.0 (compatible; YeahmarketBot/1.0)")

    def test_missing_and_server_errors_are_rejected(self) -> None:
        for status in (404, 410, 500, 503):
            with self.subTest(status=status), patch("bot.validation.urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value = MagicMock(status=status)
                valid, message = check_product_link("https://example.com/item")
                self.assertFalse(valid)
                self.assertIn(str(status), message)

    def test_403_405_and_429_http_errors_are_accepted(self) -> None:
        for status in (403, 405, 429):
            with self.subTest(status=status), patch("bot.validation.urllib.request.urlopen", side_effect=urllib.error.HTTPError("https://example.com", status, "blocked", {}, None)):
                self.assertEqual(check_product_link("https://example.com/item"), (True, ""))

    def test_network_errors_have_actionable_message(self) -> None:
        for error in (urllib.error.URLError("offline"), TimeoutError(), OSError("offline")):
            with self.subTest(error=type(error).__name__), patch("bot.validation.urllib.request.urlopen", side_effect=error):
                valid, message = check_product_link("https://example.com/item")
                self.assertFalse(valid)
                self.assertIn("Не удалось открыть", message)
