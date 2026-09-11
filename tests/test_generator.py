import random
import unittest
from datetime import date, datetime

from support_platform import (
    ChatStatus,
    JsonStateStore,
    ValidationError,
    create_application,
    generator,
)


class GeneratorTests(unittest.TestCase):
    def test_seed_and_start_reproduce_data_without_changing_global_random_state(self):
        state = random.getstate()
        kwargs = {
            "operators": 4,
            "users": 10,
            "chats": 150,
            "seed": 42,
            "start": datetime(2026, 1, 1),
        }
        first = generator.generate_platform(**kwargs)
        second = generator.generate_platform(**kwargs)
        self.assertEqual(JsonStateStore.to_dict(first), JsonStateStore.to_dict(second))
        self.assertEqual(random.getstate(), state)
        self.assertEqual(len(first.queries.all_chats()), 150)

    def test_profiles_always_have_the_requested_age_range(self):
        rng = random.Random(42)
        for today in (date(2026, 3, 31), date(2024, 2, 29), date(2026, 2, 28), date(2026, 1, 1)):
            for minimum, maximum in ((18, 65), (18, 18), (0, 0)):
                for _ in range(200):
                    birthday = generator.random_birth_date(rng, minimum, maximum, today)
                    age = (
                        today.year
                        - birthday.year
                        - ((today.month, today.day) < (birthday.month, birthday.day))
                    )
                    self.assertTrue(minimum <= age <= maximum, (today, birthday, age))

    def test_invalid_generator_arguments_are_rejected(self):
        for kwargs in (
            {"operators": -1},
            {"users": 0},
            {"chats": -1},
            {"users": True},
            {"max_active_chats": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                generator.generate_platform(**kwargs)
        for value in (-0.1, 1.1, float("nan"), True, "0.5"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                generator.generate_chats(create_application(), 0, close_probability=value)

    def test_empty_generation_and_generation_without_operators(self):
        empty = generator.generate_platform(operators=0, users=0, chats=0)
        self.assertEqual(empty.queries.stats()["chats_total"], 0)
        waiting = generator.generate_platform(operators=0, users=1, chats=10, seed=1)
        self.assertEqual(len(waiting.queries.chats_by_status(ChatStatus.WAITING)), 10)

    def test_simulation_does_not_reuse_a_slot_before_its_chat_closed(self):
        app = generator.generate_platform(operators=1, users=1, chats=0, seed=1)
        chats = generator.generate_chats(
            app,
            30,
            start=datetime(2026, 1, 1),
            close_probability=1,
            rate_probability=1,
            rng=random.Random(1),
        )
        self.assertTrue(all(chat.is_closed and chat.csat is not None for chat in chats))
        for previous, following in zip(chats, chats[1:], strict=False):
            self.assertGreater(following.created_at, previous.closed_at)

    def test_single_word_operator_name_is_supported(self):
        self.assertEqual(generator._fill("{name}", random.Random(0), "Анна"), "Анна")
