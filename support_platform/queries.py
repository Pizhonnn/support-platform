from collections import Counter, defaultdict
from typing import Any

from .exceptions import ValidationError
from .models import CSAT_MAX, CSAT_MIN, Chat, ChatStatus, Operator, User
from .repositories import Repositories


class PlatformQueries:
    def __init__(self, repositories: Repositories) -> None:
        self._repositories = repositories

    def get_operator(self, operator_id: int) -> Operator:
        return self._repositories.operators.get(operator_id)

    def get_user(self, user_id: int) -> User:
        return self._repositories.users.get(user_id)

    def get_chat(self, chat_id: int) -> Chat:
        return self._repositories.chats.get(chat_id)

    def all_operators(self) -> list[Operator]:
        return self._repositories.operators.list()

    def all_users(self) -> list[User]:
        return self._repositories.users.list()

    def all_chats(self) -> list[Chat]:
        return self._repositories.chats.list()

    def chats_by_operator(self, operator_id: int) -> list[Chat]:
        self.get_operator(operator_id)
        return self._repositories.chats.by_operator(operator_id)

    def chats_by_user(self, user_id: int) -> list[Chat]:
        self.get_user(user_id)
        return self._repositories.chats.by_user(user_id)

    def chats_by_status(self, status: ChatStatus) -> list[Chat]:
        if not isinstance(status, ChatStatus):
            raise ValidationError("Ожидается значение ChatStatus")
        return self._repositories.chats.by_status(status)

    def waiting_ids(self) -> list[int]:
        return self._repositories.chats.waiting_ids()

    def active_chat_ids(self) -> dict[int, list[int]]:
        result: dict[int, list[int]] = defaultdict(list)
        for chat in self.chats_by_status(ChatStatus.OPEN):
            if chat.operator_id is not None:
                result[chat.operator_id].append(chat.id)
        return dict(result)

    def operator_stats(self) -> dict[int, dict[str, Any]]:
        totals: Counter[int] = Counter()
        closed: Counter[int] = Counter()
        scores: Counter[int] = Counter()
        ratings: Counter[int] = Counter()
        for chat in self.all_chats():
            if chat.operator_id is None:
                continue
            totals[chat.operator_id] += 1
            closed[chat.operator_id] += chat.is_closed
            if chat.csat is not None:
                scores[chat.operator_id] += chat.csat
                ratings[chat.operator_id] += 1
        return {
            operator.id: {
                "chats_total": totals[operator.id],
                "chats_closed": closed[operator.id],
                "avg_csat": round(scores[operator.id] / ratings[operator.id], 2)
                if ratings[operator.id]
                else None,
            }
            for operator in self.all_operators()
        }

    def user_chat_counts(self) -> dict[int, int]:
        return dict(Counter(chat.user_id for chat in self.all_chats()))

    def stats(self) -> dict[str, Any]:
        chats = self.all_chats()
        statuses: Counter[str] = Counter()
        distribution: Counter[int] = Counter()
        scores: Counter[int] = Counter()
        ratings: Counter[int] = Counter()
        closed_without_csat = 0
        for chat in chats:
            statuses[chat.status.value] += 1
            if chat.csat is not None:
                distribution[chat.csat] += 1
                if chat.operator_id is not None:
                    scores[chat.operator_id] += chat.csat
                    ratings[chat.operator_id] += 1
            elif chat.is_closed:
                closed_without_csat += 1
        rated_count = sum(distribution.values())
        operators = self.all_operators()
        return {
            "operators": len(operators),
            "users": len(self.all_users()),
            "chats_total": len(chats),
            "chats_by_status": {status.value: statuses[status.value] for status in ChatStatus},
            "chats_closed_without_csat": closed_without_csat,
            "csat_distribution": {
                score: distribution[score] for score in range(CSAT_MIN, CSAT_MAX + 1)
            },
            "avg_csat": round(
                sum(score * count for score, count in distribution.items()) / rated_count, 2
            )
            if rated_count
            else None,
            "avg_csat_by_operator": {
                operator.id: round(scores[operator.id] / ratings[operator.id], 2)
                if ratings[operator.id]
                else None
                for operator in operators
            },
            "waiting_queue": self.waiting_ids(),
        }
