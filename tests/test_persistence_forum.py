from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bot import forum, persistence
from bot.config import settings
from bot.state import BotState


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.paths = {
            "forum_threads": root / "threads.json",
            "message_links": root / "links.json",
            "order_counter": root / "counter.txt",
        }
        self.test_settings = replace(settings, **self.paths)
        self.settings_patch = patch("bot.persistence.settings", self.test_settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def test_save_and_load_restores_thread_reverse_mapping_and_message_links(self) -> None:
        state = BotState()
        state.forum_threads = {10: 101}
        state.message_links = {501: {"customer_chat_id": 10, "customer_message_id": 77}}
        persistence.save(state)
        persistence.save_message_links(state)

        restored = BotState()
        persistence.load(restored)

        self.assertEqual(restored.forum_threads, {10: 101})
        self.assertEqual(restored.thread_users, {101: 10})
        self.assertEqual(restored.message_links, {501: {"customer_chat_id": 10, "customer_message_id": 77}})

    def test_load_tolerates_missing_and_invalid_json_files(self) -> None:
        self.paths["forum_threads"].write_text("not json", encoding="utf-8")
        self.paths["message_links"].write_text("[]", encoding="utf-8")
        state = BotState()

        persistence.load(state)

        self.assertEqual(state.forum_threads, {})
        self.assertEqual(state.message_links, {})

    def test_load_ignores_non_numeric_persisted_identifiers(self) -> None:
        self.paths["forum_threads"].write_text(json.dumps({"bad": "thread", "1": "2"}), encoding="utf-8")
        self.paths["message_links"].write_text(json.dumps({"bad": {"customer_chat_id": "3"}, "4": {"customer_chat_id": "bad"}}), encoding="utf-8")
        state = BotState()

        persistence.load(state)

        self.assertEqual(state.forum_threads, {1: 2})
        self.assertEqual(state.message_links, {})

    def test_load_ignores_link_without_customer_identifier(self) -> None:
        self.paths["forum_threads"].write_text("{}", encoding="utf-8")
        self.paths["message_links"].write_text(json.dumps({"1": {}, "2": {"customer_chat_id": "20", "customer_message_id": None}}), encoding="utf-8")
        state = BotState()

        persistence.load(state)

        self.assertEqual(state.message_links, {2: {"customer_chat_id": 20, "customer_message_id": None}})

    def test_order_counter_starts_at_one_and_increments(self) -> None:
        self.assertEqual(persistence.next_order_number(), 1)
        self.assertEqual(persistence.next_order_number(), 2)
        self.assertEqual(self.paths["order_counter"].read_text(encoding="utf-8"), "2")

    def test_invalid_order_counter_is_recovered(self) -> None:
        self.paths["order_counter"].write_text("broken", encoding="utf-8")
        self.assertEqual(persistence.next_order_number(), 1)

    def test_save_creates_missing_state_directory(self) -> None:
        nested = Path(self.temp_dir.name) / "missing" / "state"
        test_settings = replace(
            self.test_settings,
            forum_threads=nested / "threads.json",
            message_links=nested / "links.json",
            order_counter=nested / "counter.txt",
        )
        with patch("bot.persistence.settings", test_settings):
            state = BotState()
            persistence.save(state)
            persistence.save_message_links(state)
            persistence.next_order_number()

        self.assertTrue((nested / "threads.json").exists())
        self.assertTrue((nested / "links.json").exists())
        self.assertEqual((nested / "counter.txt").read_text(encoding="utf-8"), "1")


class ForumTests(unittest.TestCase):
    def test_client_label_prefers_escaped_username(self) -> None:
        state = BotState()
        state.customer_profiles[3] = {"username": " @a<b> ", "first_name": "Ignored"}

        self.assertEqual(forum.client_label(state, 3), "@a&lt;b&gt;")

    def test_client_label_falls_back_to_escaped_user_link(self) -> None:
        state = BotState()
        state.customer_profiles[3] = {"first_name": "Ann <", "last_name": "O'Brien"}

        self.assertEqual(forum.client_label(state, 3), '<a href="tg://user?id=3">Ann &lt; O&#x27;Brien</a>')

    def test_get_or_create_topic_reuses_existing_topic(self) -> None:
        state = BotState()
        state.forum_threads[7] = 70
        with patch("bot.forum.request") as request:
            self.assertEqual(forum.get_or_create_topic(state, 7, {}), 70)
        request.assert_not_called()

    def test_get_or_create_topic_persists_new_bidirectional_mapping(self) -> None:
        state = BotState()
        with patch("bot.forum.request", return_value={"message_thread_id": 70}) as request, patch("bot.forum.next_order_number", return_value=9), patch("bot.forum.save") as save:
            thread_id = forum.get_or_create_topic(state, 7, {"platform": "A&B", "category": "X"})

        self.assertEqual(thread_id, 70)
        self.assertEqual(state.forum_threads, {7: 70})
        self.assertEqual(state.thread_users, {70: 7})
        self.assertEqual(request.call_args.args[0], "createForumTopic")
        self.assertIn("Заявка 9 | A&B", request.call_args.args[1]["name"])
        save.assert_called_once_with(state)

    def test_submit_order_formats_escapes_and_links_text_and_photo(self) -> None:
        state = BotState()
        state.customer_profiles[7] = {"username": "buyer"}
        item = {"platform": "A&B", "currency": "CNY", "delivery": "air", "link": "https://e.test/?a=1&b=2", "quantity": "2", "size": "M<", "price": "12.50", "photo_message_id": "33"}
        with patch("bot.forum.get_or_create_topic", return_value=70), patch("bot.forum.send_message", return_value={"message_id": 500}) as send, patch("bot.forum.request", return_value={"message_id": 501}) as request, patch("bot.forum.save_message_links") as save_links:
            self.assertEqual(forum.submit_order(state, 7, [item]), 70)

        text = send.call_args.args[1]
        self.assertIn("A&amp;B", text)
        self.assertNotIn("Категория", text)
        self.assertIn("25.00 CNY", text)
        self.assertIn("14 ₽", text)
        self.assertIn("a=1&amp;b=2", text)
        self.assertEqual(request.call_args.args[0], "copyMessage")
        self.assertEqual(state.message_links[500]["customer_message_id"], None)
        self.assertEqual(state.message_links[501]["customer_message_id"], 33)
        self.assertEqual(save_links.call_count, 2)

    def test_submit_question_escapes_text_and_uses_customer_topic(self) -> None:
        state = BotState()
        with patch("bot.forum.get_or_create_topic", return_value=70), patch("bot.forum.send_message") as send:
            forum.submit_question(state, 7, "<hello>")

        self.assertIn("&lt;hello&gt;", send.call_args.args[1])
        self.assertEqual(send.call_args.kwargs["message_thread_id"], 70)

    def test_relay_customer_and_manager_record_synchronized_links(self) -> None:
        state = BotState()
        with patch("bot.forum.request", return_value={"message_id": 12}) as request, patch("bot.forum.save_message_links") as save:
            forum.relay_customer({"chat": {"id": 7}, "message_id": 8}, 70, state)
            forum.relay_manager({"chat": {"id": -1}, "message_id": 9}, 7, state)

        self.assertEqual(state.message_links[12], {"customer_chat_id": 7, "customer_message_id": 8})
        self.assertEqual(state.message_links[9], {"customer_chat_id": 7, "customer_message_id": 12})
        self.assertEqual(request.call_count, 2)
        self.assertEqual(save.call_count, 2)

    def test_delete_forum_message_deletes_customer_copy_and_command(self) -> None:
        state = BotState()
        state.message_links[50] = {"customer_chat_id": 7, "customer_message_id": 8}
        with patch("bot.forum.request") as request, patch("bot.forum.save_message_links") as save:
            forum.delete_forum_message_and_copy(state, {"message_id": 51, "reply_to_message": {"message_id": 50}})

        self.assertEqual(state.message_links, {})
        self.assertEqual(request.call_count, 3)
        request.assert_any_call("deleteMessage", {"chat_id": settings.forum_chat_id, "message_id": 50})
        request.assert_any_call("deleteMessage", {"chat_id": 7, "message_id": 8})
        save.assert_called_once_with(state)
