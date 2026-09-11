import unittest
from datetime import datetime, timedelta

from support_platform import Chat, ChatStateError, Message, SenderType, ValidationError


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1)
        self.chat = Chat(1, 2, self.now)

    def test_sender_must_belong_to_chat_even_when_ids_overlap_between_roles(self):
        self.chat.assign(3)
        for role, sender_id in ((SenderType.USER, 3), (SenderType.OPERATOR, 2)):
            with self.subTest(role=role), self.assertRaises(ValidationError):
                self.chat.add_message(Message(role, sender_id, "Сообщение", self.now))
        self.assertEqual(self.chat.messages, [])

    def test_event_cannot_precede_creation_even_without_history(self):
        with self.assertRaises(ValidationError):
            self.chat.add_message(
                Message(SenderType.USER, 2, "Сообщение", self.now - timedelta(seconds=1))
            )
        self.assertEqual(self.chat.messages, [])

    def test_chat_cannot_be_reassigned(self):
        self.chat.assign(3)
        with self.assertRaises(ChatStateError):
            self.chat.assign(4)
        self.assertEqual(self.chat.operator_id, 3)

    def test_restored_history_must_be_chronological(self):
        with self.assertRaises(ValidationError):
            Chat(
                1,
                2,
                self.now,
                messages=[
                    Message(SenderType.USER, 2, "Первое", self.now + timedelta(minutes=1)),
                    Message(SenderType.USER, 2, "Второе", self.now),
                ],
            )
