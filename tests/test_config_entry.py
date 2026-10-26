from __future__ import annotations

import os
import runpy
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bot import config


class ConfigTests(unittest.TestCase):
    def test_load_env_file_reads_valid_values_and_does_not_overwrite_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("# comment\nFIRST=value\nQUOTED='hello world'\nINVALID\nEXISTS=from-file\n", encoding="utf-8")
            with patch.object(config, "ROOT", root), patch.dict(os.environ, {"EXISTS": "already"}, clear=True):
                config.load_env_file()
                self.assertEqual(os.environ["FIRST"], "value")
                self.assertEqual(os.environ["QUOTED"], "hello world")
                self.assertEqual(os.environ["EXISTS"], "already")
                self.assertNotIn("INVALID", os.environ)

    def test_load_env_file_allows_absent_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(config, "ROOT", Path(directory)):
            config.load_env_file()

    def test_settings_api_url_uses_token(self) -> None:
        self.assertEqual(replace(config.settings, token="secret").api_url, "https://api.telegram.org/botsecret")

    def test_settings_do_not_include_a_welcome_image(self) -> None:
        self.assertFalse(hasattr(config.settings, "welcome_image"))


class EntryPointTests(unittest.TestCase):
    def test_main_invokes_runtime_when_executed_as_script(self) -> None:
        with patch("bot.runtime.run") as run:
            runpy.run_path(str(config.ROOT / "main.py"), run_name="__main__")
        run.assert_called_once_with()
