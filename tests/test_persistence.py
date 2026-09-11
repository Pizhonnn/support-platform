import json
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from support_platform import JsonStateStore, ValidationError, create_application
from support_platform.json_io import write_json

from .test_platform import PROFILE


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = JsonStateStore()
        self.app = create_application(clock=lambda: datetime(2026, 1, 1))
        self.user = self.app.profiles.register_user(*PROFILE)
        self.app.platform.create_chat(self.user.id, "Первое обращение")
        self.app.platform.create_chat(self.user.id, "Второе обращение")
        self.payload = self.store.to_dict(self.app)

    def test_file_roundtrip_preserves_unicode_and_fifo(self):
        self.payload["waiting_queue"] = [2, 1]
        restored = self.store.from_dict(self.payload)
        with TemporaryDirectory() as directory:
            path = self.store.save(restored, Path(directory) / "nested" / "state.json")
            self.assertIn("Первое обращение", path.read_text(encoding="utf-8"))
            loaded = self.store.load(path)
            self.assertEqual(self.store.to_dict(loaded), self.payload)
            operator = loaded.profiles.register_operator(*PROFILE)
            self.assertEqual(loaded.queries.get_chat(2).operator_id, operator.id)
            self.assertEqual(loaded.queries.waiting_ids(), [1])

    def test_legacy_counters_cannot_overwrite_imported_records(self):
        self.payload.pop("schema_version")
        for counters in (None, {"user": 0, "chat": 0}, {"user": 999, "chat": 999}):
            with self.subTest(counters=counters):
                self.payload["counters"] = counters
                loaded = self.store.from_dict(self.payload)
                user = loaded.profiles.register_user(*PROFILE)
                chat = loaded.platform.create_chat(user.id, "Новое обращение")
                self.assertGreater(user.id, self.user.id)
                self.assertGreater(chat.id, 2)
                self.assertEqual(len(loaded.queries.all_chats()), 3)

    def test_missing_queue_is_reconstructed(self):
        self.payload.pop("waiting_queue")
        self.assertEqual(self.store.from_dict(self.payload).queries.waiting_ids(), [1, 2])

    def test_invalid_queues_are_rejected(self):
        for queue in ([1, 1], [1], [1, 999], [True, 2], None, "1,2"):
            with self.subTest(queue=queue), self.assertRaises(ValidationError):
                self.store.from_dict({**self.payload, "waiting_queue": queue})

    def test_bad_shapes_versions_and_duplicate_ids_are_rejected(self):
        for payload in (
            None,
            [],
            {},
            {**self.payload, "schema_version": 2},
            {**self.payload, "schema_version": True},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.store.from_dict(payload)
        for collection in ("users", "chats"):
            payload = deepcopy(self.payload)
            payload[collection].append(deepcopy(payload[collection][0]))
            with self.subTest(collection=collection), self.assertRaises(ValidationError):
                self.store.from_dict(payload)

    def test_invalid_references_states_messages_and_dates_are_rejected(self):
        changes = (
            {"user_id": 999},
            {"operator_id": 999, "status": "open"},
            {"csat": 5},
            {"messages": []},
            {"created_at": "tomorrow"},
            {"status": "closed"},
            {"id": True},
        )
        for fields in changes:
            payload = deepcopy(self.payload)
            payload["chats"][0].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.store.from_dict(payload)
        payload = deepcopy(self.payload)
        payload["chats"][0]["messages"][0]["sender_id"] = 999
        with self.assertRaises(ValidationError):
            self.store.from_dict(payload)

    def test_overloaded_operator_is_rejected(self):
        self.app.profiles.register_operator(*PROFILE, max_active_chats=2)
        payload = self.store.to_dict(self.app)
        payload["operators"][0]["max_active_chats"] = 1
        with self.assertRaises(ValidationError):
            self.store.from_dict(payload)

    def test_failed_write_preserves_previous_file_and_removes_temporary_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("original", encoding="utf-8")
            with patch("support_platform.json_io.json.dump", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    self.store.save(self.app, path)
            self.assertEqual(path.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(Path(directory).iterdir()), [path])
            with patch(
                "support_platform.json_io.Path.replace", side_effect=PermissionError("locked")
            ):
                with self.assertRaises(PermissionError):
                    self.store.save(self.app, path)
            self.assertEqual(path.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_atomic_write_replaces_existing_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("old", encoding="utf-8")
            write_json(path, {"text": "Готово"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"text": "Готово"})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_json_has_a_clear_error(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(ValidationError):
                self.store.load(path)
