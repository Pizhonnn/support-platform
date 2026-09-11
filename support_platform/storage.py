from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Generic

from .exceptions import DuplicateError, NotFoundError
from .models import Chat, ChatStatus, Operator, User, validate_integer
from .repositories import Repositories, T


@dataclass(slots=True)
class InMemoryDatabase:
    operators: dict[int, Operator] = field(default_factory=dict, init=False)
    users: dict[int, User] = field(default_factory=dict, init=False)
    chats: dict[int, Chat] = field(default_factory=dict, init=False)
    sequences: dict[str, int] = field(default_factory=dict, init=False)
    chats_by_user: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set), init=False)
    chats_by_operator: dict[int, set[int]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )
    chats_by_status: dict[ChatStatus, dict[int, None]] = field(
        default_factory=lambda: {status: OrderedDict() for status in ChatStatus}, init=False
    )
    chat_index_keys: dict[int, tuple[int, int | None, ChatStatus]] = field(
        default_factory=dict, init=False
    )
    active_chats_by_operator: Counter[int] = field(default_factory=Counter, init=False)


class InMemoryRepository(Generic[T]):
    def __init__(self, records: dict[int, T], sequences: dict[str, int], name: str) -> None:
        self._records: dict[int, T] = records
        self._sequences = sequences
        self._name = name
        self._sequences[name] = max(self._sequences.get(name, 0), max(records, default=0))

    def next_id(self) -> int:
        self._sequences[self._name] += 1
        return self._sequences[self._name]

    def add(self, entity: T) -> None:
        validate_integer(entity.id, "id", 1)
        if entity.id in self._records:
            raise DuplicateError(f"{self._name}: id={entity.id} уже существует")
        self._records[entity.id] = entity
        self._sequences[self._name] = max(self._sequences[self._name], entity.id)

    def get(self, entity_id: int) -> T:
        validate_integer(entity_id, "id", 1)
        try:
            return self._records[entity_id]
        except KeyError:
            raise NotFoundError(f"{self._name}: id={entity_id} не найден") from None

    def save(self, entity: T) -> None:
        self.get(entity.id)
        self._records[entity.id] = entity

    def list(self) -> list[T]:
        return [self._records[key] for key in sorted(self._records)]


class InMemoryChatRepository(InMemoryRepository[Chat]):
    def __init__(self, database: InMemoryDatabase) -> None:
        super().__init__(database.chats, database.sequences, "chat")
        self._database = database

    def add(self, entity: Chat) -> None:
        super().add(entity)
        self._index(entity)

    def save(self, entity: Chat) -> None:
        super().save(entity)
        self._index(entity)

    def _index(self, chat: Chat) -> None:
        db = self._database
        previous = db.chat_index_keys.get(chat.id)
        current = (chat.user_id, chat.operator_id, chat.status)
        if previous == current:
            return
        if previous is not None:
            user_id, operator_id, status = previous
            db.chats_by_user[user_id].discard(chat.id)
            if operator_id is not None:
                db.chats_by_operator[operator_id].discard(chat.id)
                if status == ChatStatus.OPEN:
                    db.active_chats_by_operator[operator_id] -= 1
                    if not db.active_chats_by_operator[operator_id]:
                        del db.active_chats_by_operator[operator_id]
            if status != chat.status:
                db.chats_by_status[status].pop(chat.id, None)
        db.chats_by_user[chat.user_id].add(chat.id)
        if chat.operator_id is not None:
            db.chats_by_operator[chat.operator_id].add(chat.id)
            if chat.status == ChatStatus.OPEN:
                db.active_chats_by_operator[chat.operator_id] += 1
        db.chats_by_status[chat.status][chat.id] = None
        db.chat_index_keys[chat.id] = current

    def by_user(self, user_id: int) -> list[Chat]:
        return [self._records[key] for key in sorted(self._database.chats_by_user.get(user_id, ()))]

    def by_operator(self, operator_id: int) -> list[Chat]:
        keys = self._database.chats_by_operator.get(operator_id, ())
        return [self._records[key] for key in sorted(keys)]

    def by_status(self, status: ChatStatus) -> list[Chat]:
        return [self._records[key] for key in sorted(self._database.chats_by_status[status])]

    def next_waiting(self) -> Chat | None:
        chat_id = next(iter(self._database.chats_by_status[ChatStatus.WAITING]), None)
        return self._records[chat_id] if chat_id is not None else None

    def waiting_ids(self) -> list[int]:
        return list(self._database.chats_by_status[ChatStatus.WAITING])

    def active_counts(self) -> dict[int, int]:
        return dict(self._database.active_chats_by_operator)


def memory_repositories(database: InMemoryDatabase) -> Repositories:
    return Repositories(
        operators=InMemoryRepository(database.operators, database.sequences, "operator"),
        users=InMemoryRepository(database.users, database.sequences, "user"),
        chats=InMemoryChatRepository(database),
    )
