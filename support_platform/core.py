from collections.abc import Callable
from datetime import datetime
from random import Random

from .exceptions import ChatStateError
from .models import Chat, Message, Operator, SenderType, validate_datetime
from .repositories import Repositories


class SupportPlatform:
    def __init__(
        self,
        repositories: Repositories,
        rng: Random | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repositories = repositories
        self._rng = rng if rng is not None else Random()
        self._clock = clock

    def _now(self, at: datetime | None) -> datetime:
        moment = self._clock() if at is None else at
        validate_datetime(moment)
        return moment.replace(microsecond=0)

    def _available_operators(self, counts: dict[int, int]) -> list[Operator]:
        return [
            operator
            for operator in self._repositories.operators.list()
            if counts.get(operator.id, 0) < operator.max_active_chats
        ]

    def dispatch_queue(self) -> None:
        chats = self._repositories.chats
        if chats.next_waiting() is None:
            return
        counts = chats.active_counts()
        candidates = self._available_operators(counts)
        while candidates:
            chat = chats.next_waiting()
            if chat is None:
                break
            operator = self._rng.choice(candidates)
            chat.assign(operator.id)
            chats.save(chat)
            counts[operator.id] = counts.get(operator.id, 0) + 1
            if counts[operator.id] == operator.max_active_chats:
                candidates.remove(operator)

    def create_chat(self, user_id: int, text: str, at: datetime | None = None) -> Chat:
        user = self._repositories.users.get(user_id)
        now = self._now(at)
        message = Message(SenderType.USER, user.id, text, now)
        chats = self._repositories.chats
        chat = Chat(id=chats.next_id(), user_id=user.id, created_at=now)
        chat.add_message(message)
        candidates = self._available_operators(chats.active_counts())
        if candidates:
            chat.assign(self._rng.choice(candidates).id)
        chats.add(chat)
        return chat

    def user_reply(self, chat_id: int, text: str, at: datetime | None = None) -> Message:
        chat = self._repositories.chats.get(chat_id)
        message = Message(SenderType.USER, chat.user_id, text, self._now(at))
        chat.add_message(message)
        self._repositories.chats.save(chat)
        return message

    def operator_reply(self, chat_id: int, text: str, at: datetime | None = None) -> Message:
        chat = self._repositories.chats.get(chat_id)
        if chat.operator_id is None:
            raise ChatStateError("Чат ожидает назначения оператора")
        message = Message(SenderType.OPERATOR, chat.operator_id, text, self._now(at))
        chat.add_message(message)
        self._repositories.chats.save(chat)
        return message

    def close_chat(self, chat_id: int, at: datetime | None = None) -> Chat:
        chat = self._repositories.chats.get(chat_id)
        chat.close(self._now(at))
        self._repositories.chats.save(chat)
        self.dispatch_queue()
        return chat

    def rate_chat(self, chat_id: int, csat: int) -> Chat:
        chat = self._repositories.chats.get(chat_id)
        chat.rate(csat)
        self._repositories.chats.save(chat)
        return chat
