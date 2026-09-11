import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from support_platform import Exporter, JsonStateStore, create_application

from .test_platform import PROFILE


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.app = create_application(clock=lambda: datetime(2026, 1, 1))
        self.operator = self.app.profiles.register_operator(*PROFILE)
        self.user = self.app.profiles.register_user(*PROFILE)
        self.first = self.app.platform.create_chat(self.user.id, "Нужна помощь")
        self.app.platform.close_chat(self.first.id)
        self.app.platform.rate_chat(self.first.id, 5)
        self.second = self.app.platform.create_chat(self.user.id, "Ещё вопрос")
        self.waiting = self.app.platform.create_chat(self.user.id, "Ожидаю")

    def test_all_export_types_have_consistent_totals_and_do_not_mutate_data(self):
        before = JsonStateStore.to_dict(self.app)
        with TemporaryDirectory() as directory:
            exporter = Exporter(self.app.queries, directory, quiet=True)
            exporter.export_everything()
            files = {
                path.name: json.loads(path.read_text(encoding="utf-8"))
                for path in Path(directory).glob("*.json")
            }
            self.assertEqual(len(files), 5)
            for payload in files.values():
                self.assertEqual(payload["count"], len(payload["items"]))
            self.assertEqual(files["all_chats.json"]["count"], 3)
            self.assertEqual(files["chats_operator_1.json"]["count"], 2)
            self.assertEqual(files["chats_user_1.json"]["count"], 3)
            operator = files["operators.json"]["items"][0]
            self.assertEqual(
                (operator["chats_total"], operator["chats_closed"], operator["avg_csat"]),
                (2, 1, 5.0),
            )
            self.assertEqual(operator["active_chat_ids"], [self.second.id])
            self.assertFalse(operator["is_free"])
            self.assertEqual(files["users.json"]["items"][0]["chats_total"], 3)
            self.assertIsNone(files["all_chats.json"]["items"][-1]["operator_name"])
            self.assertEqual(files["all_chats.json"]["items"][0]["user_name"], PROFILE[0])
        self.assertEqual(JsonStateStore.to_dict(self.app), before)

    def test_export_names_reflect_profile_updates(self):
        self.app.profiles.update_user(self.user.id, full_name="Новое имя")
        self.app.profiles.update_operator(self.operator.id, full_name="Другой оператор")
        with TemporaryDirectory() as directory:
            items = Exporter(self.app.queries, directory, quiet=True).export_all_chats()["items"]
            self.assertEqual(items[0]["user_name"], "Новое имя")
            self.assertEqual(items[0]["operator_name"], "Другой оператор")

    def test_empty_exports_and_console_output(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()) as stream:
            exporter = Exporter(create_application().queries, directory, verbose=True)
            exporter.export_everything()
            self.assertIn('"count": 0', stream.getvalue())
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 3)

    def test_verbose_console_handles_chats_and_profiles(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()) as stream:
            Exporter(self.app.queries, directory, verbose=True).export_everything()
            self.assertIn("Нужна помощь", stream.getvalue())
            self.assertIn("не назначен", stream.getvalue())
