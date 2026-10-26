from __future__ import annotations

import io
import json
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot import runtime, telegram_api
from bot.config import settings


class TelegramApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patch = patch("bot.telegram_api.settings", replace(settings, token="token-123"))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_request_requires_token(self) -> None:
        with patch("bot.telegram_api.settings", replace(settings, token="")):
            with self.assertRaisesRegex(RuntimeError, "BOT_TOKEN"):
                telegram_api.request("getMe")

    def test_request_posts_json_and_returns_result(self) -> None:
        response = MagicMock()
        response.read.return_value = b'{"ok": true, "result": {"id": 1}}'
        with patch("bot.telegram_api.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = response
            result = telegram_api.request("sendMessage", {"chat_id": 5, "text": "Привет"})
            request = urlopen.call_args.args[0]

        self.assertEqual(result, {"id": 1})
        self.assertEqual(request.full_url, "https://api.telegram.org/bottoken-123/sendMessage")
        self.assertEqual(json.loads(request.data), {"chat_id": 5, "text": "Привет"})
        self.assertEqual(request.get_method(), "POST")

    def test_request_converts_http_and_api_errors_to_runtime_error(self) -> None:
        error = urllib.error.HTTPError("https://example.test", 401, "no", {}, io.BytesIO(b"denied"))
        with patch("bot.telegram_api.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
                telegram_api.request("getMe")
        response = MagicMock()
        response.read.return_value = b'{"ok": false, "description": "bad"}'
        with patch("bot.telegram_api.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = response
            with self.assertRaisesRegex(RuntimeError, "Telegram API error"):
                telegram_api.request("getMe")

    def test_send_message_builds_optional_payload_fields(self) -> None:
        with patch("bot.telegram_api.request", return_value={"message_id": 1}) as request:
            telegram_api.send_message(5, "text", reply_markup={"keyboard": []}, message_thread_id=9)
            telegram_api.send_message(5, "text", remove_keyboard=True)

        self.assertEqual(request.call_args_list[0].args, ("sendMessage", {"chat_id": 5, "text": "text", "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": {"keyboard": []}, "message_thread_id": 9}))
        self.assertEqual(request.call_args_list[1].args[1]["reply_markup"], {"remove_keyboard": True})

    def test_send_local_photo_serializes_multipart_request(self) -> None:
        response = MagicMock()
        response.read.return_value = b'{"ok": true, "result": {"message_id": 8}}'
        with self.subTest("existing image"):
            with patch.object(Path, "read_bytes", return_value=b"image-bytes"), patch("bot.telegram_api.urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value = response
                result = telegram_api.send_local_photo(5, Path("sample.png"), "caption", remove_keyboard=True)
                request = urlopen.call_args.args[0]

        self.assertEqual(result, {"message_id": 8})
        self.assertIn(b"image-bytes", request.data)
        self.assertIn(b"remove_keyboard", request.data)
        self.assertIn(b'filename="sample.png"', request.data)

    def test_send_local_photo_rejects_api_error(self) -> None:
        response = MagicMock()
        response.read.return_value = b'{"ok": false}'
        with patch.object(Path, "read_bytes", return_value=b"x"), patch("bot.telegram_api.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = response
            with self.assertRaisesRegex(RuntimeError, "sendPhoto"):
                telegram_api.send_local_photo(5, Path("sample.png"), "caption")


class RuntimeTests(unittest.TestCase):
    def test_run_requires_token(self) -> None:
        with patch("bot.runtime.settings", replace(settings, token="")):
            with self.assertRaisesRegex(SystemExit, "BOT_TOKEN"):
                runtime.run()

    def test_run_configures_commands_processes_updates_and_advances_offset(self) -> None:
        update = {"update_id": 4, "message": {"chat": {"id": 1}, "text": "/start"}}
        requests = [{}, [update], RuntimeError("stop")]
        with patch("bot.runtime.settings", replace(settings, token="token")), patch("bot.runtime.load") as load, patch("bot.runtime.handle_update") as handle, patch("bot.runtime.request", side_effect=requests) as request, patch("bot.runtime.log"), patch("bot.runtime.time.sleep", side_effect=StopIteration):
            with self.assertRaises(StopIteration):
                runtime.run()

        load.assert_called_once()
        handle.assert_called_once()
        self.assertEqual(request.call_args_list[0].args[0], "setMyCommands")
        self.assertEqual(request.call_args_list[1].args, ("getUpdates", {"offset": 0, "timeout": 25, "allowed_updates": ["message"]}))
        self.assertEqual(request.call_args_list[2].args, ("getUpdates", {"offset": 5, "timeout": 25, "allowed_updates": ["message"]}))
