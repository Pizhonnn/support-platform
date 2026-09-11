import random
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

from support_platform import (
    ChatStateError,
    ChatStatus,
    InMemoryDatabase,
    JsonStateStore,
    NotFoundError,
    ValidationError,
    create_application,
    memory_repositories,
)

from .fakes import detached_repositories

NOW = datetime(2026, 1, 15, 12)
PROFILE = ("Иван Иванов", "Киев", "1990-05-10", "Специалист", 4)


class MemoryPlatformTests(unittest.TestCase):
    def make_repositories(self):
        return memory_repositories(InMemoryDatabase())

    def setUp(self):
        self.app = create_application(
            self.make_repositories(), rng=random.Random(7), clock=lambda: NOW
        )
        self.user = self.app.profiles.register_user(*PROFILE)

    def operator(self, capacity=1):
        return self.app.profiles.register_operator(*PROFILE, max_active_chats=capacity)

    def chat(self):
        return self.app.platform.create_chat(self.user.id, "Нужна помощь")

    def test_complete_lifecycle_is_persisted(self):
        operator = self.operator()
        chat = self.chat()
        self.app.platform.operator_reply(chat.id, "Помогаю")
        self.app.platform.user_reply(chat.id, "Спасибо")
        self.app.platform.close_chat(chat.id)
        self.app.platform.rate_chat(chat.id, 5)
        saved = self.app.queries.get_chat(chat.id)
        self.assertEqual(
            (saved.status, saved.operator_id, saved.csat), (ChatStatus.CLOSED, operator.id, 5)
        )
        self.assertEqual(
            [message.text for message in saved.messages], ["Нужна помощь", "Помогаю", "Спасибо"]
        )
        self.assertEqual(saved.closed_at, NOW)
        self.assertEqual(self.app.repositories.chats.active_counts(), {})

    def test_queue_is_fifo_and_reply_does_not_reorder_it(self):
        self.operator()
        first, second, third = self.chat(), self.chat(), self.chat()
        self.app.platform.user_reply(second.id, "Дополнение")
        self.assertEqual(self.app.queries.waiting_ids(), [second.id, third.id])
        self.app.platform.close_chat(first.id)
        self.assertEqual(self.app.queries.get_chat(second.id).status, ChatStatus.OPEN)
        self.assertEqual(self.app.queries.waiting_ids(), [third.id])
        self.app.platform.close_chat(second.id)
        self.assertEqual(self.app.queries.get_chat(third.id).status, ChatStatus.OPEN)
        self.assertEqual(self.app.queries.waiting_ids(), [])

    def test_new_operator_takes_waiting_chats_up_to_capacity(self):
        chats = [self.chat() for _ in range(4)]
        operator = self.operator(3)
        self.assertEqual(self.app.repositories.chats.active_counts(), {operator.id: 3})
        self.assertEqual(self.app.queries.waiting_ids(), [chats[-1].id])
        self.operator()
        self.assertEqual(self.app.queries.waiting_ids(), [])

    def test_busy_operator_never_receives_another_chat(self):
        first_operator = self.operator(2)
        self.chat()
        self.chat()
        second_operator = self.operator()
        self.assertEqual(self.chat().operator_id, second_operator.id)
        self.assertEqual(self.chat().status, ChatStatus.WAITING)
        self.assertEqual(
            self.app.repositories.chats.active_counts(),
            {first_operator.id: 2, second_operator.id: 1},
        )

    def test_waiting_chat_cannot_be_closed_rated_or_answered_by_operator(self):
        chat = self.chat()
        for method, args in (
            (self.app.platform.close_chat, (chat.id,)),
            (self.app.platform.rate_chat, (chat.id, 5)),
            (self.app.platform.operator_reply, (chat.id, "Ответ")),
        ):
            with self.subTest(method=method.__name__), self.assertRaises(ChatStateError):
                method(*args)
        self.assertEqual(self.app.queries.get_chat(chat.id).status, ChatStatus.WAITING)

    def test_closed_chat_rejects_replies_second_close_and_second_rating(self):
        self.operator()
        chat = self.chat()
        self.app.platform.close_chat(chat.id)
        self.app.platform.rate_chat(chat.id, 4)
        for method, args in (
            (self.app.platform.close_chat, (chat.id,)),
            (self.app.platform.user_reply, (chat.id, "Ещё вопрос")),
            (self.app.platform.operator_reply, (chat.id, "Ответ")),
            (self.app.platform.rate_chat, (chat.id, 5)),
        ):
            with self.subTest(method=method.__name__), self.assertRaises(ChatStateError):
                method(*args)
        saved = self.app.queries.get_chat(chat.id)
        self.assertEqual((saved.csat, len(saved.messages)), (4, 1))

    def test_invalid_ratings_do_not_change_chat(self):
        self.operator()
        chat = self.chat()
        self.app.platform.close_chat(chat.id)
        for score in (True, False, 0, 6, 4.5, "5", None):
            with self.subTest(score=score), self.assertRaises(ValidationError):
                self.app.platform.rate_chat(chat.id, score)
        self.assertIsNone(self.app.queries.get_chat(chat.id).csat)

    def test_profile_update_validates_all_fields_before_saving(self):
        with self.assertRaises(ValidationError):
            self.app.profiles.update_user(self.user.id, city="Львов", experience_years=-1)
        self.assertEqual(self.app.queries.get_user(self.user.id), self.user)
        updated = self.app.profiles.update_user(self.user.id, city="Львов", birth_date="1992-02-29")
        self.assertEqual(updated.city, "Львов")
        self.assertEqual(self.app.queries.get_user(self.user.id), updated)
        self.assertNotEqual(self.user, updated)
        with self.assertRaises(FrozenInstanceError):
            updated.city = "Одесса"

    def test_profile_update_rejects_protected_and_unknown_fields(self):
        operator = self.operator()
        for fields in ({"id": 50}, {"max_active_chats": 10}, {"unknown": 1}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.app.profiles.update_operator(operator.id, **fields)
        updated = self.app.profiles.update_operator(operator.id, position="Старший специалист")
        self.assertEqual(self.app.queries.get_operator(operator.id), updated)

    def test_registration_rejects_invalid_profiles_and_capacities(self):
        for capacity in (0, -1, True, 1.5, "3"):
            with self.subTest(capacity=capacity), self.assertRaises(ValidationError):
                self.operator(capacity)
        for experience in (-1, True, "2", 2.5):
            with self.subTest(experience=experience), self.assertRaises(ValidationError):
                self.app.profiles.register_user(*PROFILE[:-1], experience)
        for birth_date in ("2020-02-30", "3000-01-01", datetime(1990, 1, 1), None):
            with self.subTest(birth_date=birth_date), self.assertRaises(ValidationError):
                self.app.profiles.register_user(PROFILE[0], PROFILE[1], birth_date, *PROFILE[3:])
        self.assertEqual(self.app.queries.all_operators(), [])
        self.assertEqual(len(self.app.queries.all_users()), 1)

    def test_empty_messages_and_invalid_time_do_not_change_history(self):
        self.operator()
        chat = self.chat()
        for text in ("", "   ", None, 3):
            with self.subTest(text=text), self.assertRaises(ValidationError):
                self.app.platform.user_reply(chat.id, text)
        for at in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=UTC), "yesterday"):
            with self.subTest(at=at), self.assertRaises(ValidationError):
                self.app.platform.operator_reply(chat.id, "Ответ", at=at)
        with self.assertRaises(ValidationError):
            self.app.platform.close_chat(chat.id, at=NOW - timedelta(seconds=1))
        self.assertEqual(len(self.app.queries.get_chat(chat.id).messages), 1)
        self.assertEqual(self.app.queries.get_chat(chat.id).status, ChatStatus.OPEN)

    def test_missing_entities_and_invalid_ids_raise_domain_errors(self):
        for method in (
            self.app.queries.get_user,
            self.app.queries.get_chat,
            self.app.queries.get_operator,
        ):
            with self.subTest(method=method.__name__), self.assertRaises(NotFoundError):
                method(999)
            with self.subTest(method=method.__name__), self.assertRaises(ValidationError):
                method(True)
        with self.assertRaises(NotFoundError):
            self.app.platform.create_chat(999, "Помогите")
        self.assertEqual(self.app.queries.all_chats(), [])

    def test_queries_and_statistics_include_unassigned_and_unrated_chats(self):
        operator = self.operator()
        rated = self.chat()
        self.app.platform.close_chat(rated.id)
        self.app.platform.rate_chat(rated.id, 4)
        unrated = self.chat()
        self.app.platform.close_chat(unrated.id)
        opened, waiting = self.chat(), self.chat()
        stats = self.app.queries.stats()
        self.assertEqual(stats["chats_by_status"], {"waiting": 1, "open": 1, "closed": 2})
        self.assertEqual(stats["avg_csat"], 4.0)
        self.assertEqual(stats["chats_closed_without_csat"], 1)
        self.assertEqual(stats["csat_distribution"], {1: 0, 2: 0, 3: 0, 4: 1, 5: 0})
        self.assertEqual(stats["avg_csat_by_operator"], {operator.id: 4.0})
        self.assertEqual(self.app.queries.active_chat_ids(), {operator.id: [opened.id]})
        self.assertEqual(
            [chat.id for chat in self.app.queries.chats_by_user(self.user.id)], [1, 2, 3, 4]
        )
        self.assertEqual(
            [chat.id for chat in self.app.queries.chats_by_operator(operator.id)], [1, 2, 3]
        )
        self.assertEqual(self.app.queries.waiting_ids(), [waiting.id])
        self.assertEqual(
            self.app.queries.operator_stats()[operator.id],
            {"chats_total": 3, "chats_closed": 2, "avg_csat": 4.0},
        )

    def test_new_applications_are_isolated(self):
        other = create_application()
        self.assertEqual(other.queries.all_users(), [])
        self.assertEqual(other.queries.stats()["avg_csat"], None)

    def test_snapshot_roundtrip_preserves_lifecycle(self):
        self.operator()
        first, second = self.chat(), self.chat()
        payload = JsonStateStore.to_dict(self.app)
        restored = JsonStateStore.from_dict(payload)
        self.assertEqual(JsonStateStore.to_dict(restored), payload)
        restored.platform.close_chat(first.id, at=NOW)
        self.assertEqual(restored.queries.get_chat(second.id).status, ChatStatus.OPEN)


class DetachedPlatformTests(MemoryPlatformTests):
    def make_repositories(self):
        return detached_repositories()
