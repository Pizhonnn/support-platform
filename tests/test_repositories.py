import unittest
from dataclasses import replace
from datetime import date, datetime

from support_platform import (
    Chat,
    ChatStatus,
    DuplicateError,
    InMemoryDatabase,
    NotFoundError,
    User,
    memory_repositories,
)

from .fakes import detached_repositories


class MemoryRepositoryTests(unittest.TestCase):
    def make_repositories(self):
        return memory_repositories(InMemoryDatabase())

    def setUp(self):
        self.repositories = self.make_repositories()

    def user(self, entity_id):
        return User(entity_id, "Анна Иванова", "Киев", date(1995, 1, 20), "Бухгалтер", 6)

    def test_ids_follow_imported_records_without_overwriting_them(self):
        users = self.repositories.users
        users.add(self.user(50))
        users.add(self.user(3))
        self.assertEqual(users.next_id(), 51)
        self.assertEqual([user.id for user in users.list()], [3, 50])
        with self.assertRaises(DuplicateError):
            users.add(replace(self.user(50), city="Львов"))
        self.assertEqual(users.get(50).city, "Киев")

    def test_save_requires_an_existing_record(self):
        users = self.repositories.users
        with self.assertRaises(NotFoundError):
            users.save(self.user(1))
        users.add(self.user(1))
        users.save(replace(self.user(1), city="Одесса"))
        self.assertEqual(users.get(1).city, "Одесса")

    def test_status_and_assignment_indexes_follow_saved_transitions(self):
        chats = self.repositories.chats
        chat = Chat(1, 5, datetime(2026, 1, 1))
        chats.add(chat)
        chat = chats.get(chat.id)
        chat.assign(3)
        chats.save(chat)
        self.assertEqual(chats.waiting_ids(), [])
        self.assertEqual([item.id for item in chats.by_operator(3)], [1])
        self.assertEqual(chats.active_counts(), {3: 1})
        chat.close(datetime(2026, 1, 1))
        chats.save(chat)
        chats.save(chat)
        self.assertEqual(chats.active_counts(), {})
        self.assertEqual(chats.by_status(ChatStatus.OPEN), [])
        self.assertEqual([item.id for item in chats.by_status(ChatStatus.CLOSED)], [1])
        self.assertEqual([item.id for item in chats.by_user(5)], [1])

    def test_returned_collections_do_not_expose_storage_containers(self):
        self.repositories.users.add(self.user(1))
        self.repositories.users.list().clear()
        self.assertEqual(len(self.repositories.users.list()), 1)
        self.repositories.chats.add(Chat(1, 1, datetime(2026, 1, 1)))
        self.repositories.chats.waiting_ids().clear()
        self.assertEqual(self.repositories.chats.waiting_ids(), [1])


class DetachedRepositoryTests(MemoryRepositoryTests):
    def make_repositories(self):
        return detached_repositories()

    def test_mutations_require_an_explicit_save(self):
        chats = self.repositories.chats
        chats.add(Chat(1, 1, datetime(2026, 1, 1)))
        chats.get(1).assign(1)
        self.assertEqual(chats.get(1).status, ChatStatus.WAITING)


class SharedStorageTests(unittest.TestCase):
    def test_two_repository_sets_share_sequences_and_indexes(self):
        database = InMemoryDatabase()
        first = memory_repositories(database)
        second = memory_repositories(database)
        self.assertEqual(first.chats.next_id(), 1)
        self.assertEqual(second.chats.next_id(), 2)
        first.chats.add(Chat(1, 1, datetime(2026, 1, 1)))
        second.chats.add(Chat(2, 1, datetime(2026, 1, 1)))
        self.assertEqual(first.chats.waiting_ids(), [1, 2])
        chat = second.chats.get(1)
        chat.assign(1)
        second.chats.save(chat)
        self.assertEqual(first.chats.waiting_ids(), [2])
        self.assertEqual(first.chats.active_counts(), {1: 1})
