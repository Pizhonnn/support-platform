from collections import Counter
from copy import deepcopy
from typing import Generic

from support_platform import Chat, ChatStatus, DuplicateError, NotFoundError, Repositories
from support_platform.models import validate_integer
from support_platform.repositories import T


class DetachedRepository(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []
        self._sequence = 0

    def next_id(self) -> int:
        self._sequence += 1
        return self._sequence

    def add(self, entity: T) -> None:
        if any(item.id == entity.id for item in self._items):
            raise DuplicateError(str(entity.id))
        self._items.append(deepcopy(entity))
        self._sequence = max(self._sequence, entity.id)

    def get(self, entity_id: int) -> T:
        validate_integer(entity_id, "id", 1)
        for entity in self._items:
            if entity.id == entity_id:
                return deepcopy(entity)
        raise NotFoundError(str(entity_id))

    def save(self, entity: T) -> None:
        for index, existing in enumerate(self._items):
            if existing.id == entity.id:
                self._items[index] = deepcopy(entity)
                return
        raise NotFoundError(str(entity.id))

    def list(self) -> list[T]:
        return sorted(deepcopy(self._items), key=lambda item: item.id)


class DetachedChatRepository(DetachedRepository[Chat]):
    def by_user(self, user_id: int) -> list[Chat]:
        return [chat for chat in self.list() if chat.user_id == user_id]

    def by_operator(self, operator_id: int) -> list[Chat]:
        return [chat for chat in self.list() if chat.operator_id == operator_id]

    def by_status(self, status: ChatStatus) -> list[Chat]:
        return [chat for chat in self.list() if chat.status == status]

    def waiting_ids(self) -> list[int]:
        return [chat.id for chat in self._items if chat.status == ChatStatus.WAITING]

    def next_waiting(self) -> Chat | None:
        waiting = self.waiting_ids()
        return self.get(waiting[0]) if waiting else None

    def active_counts(self) -> dict[int, int]:
        return dict(
            Counter(
                chat.operator_id
                for chat in self.by_status(ChatStatus.OPEN)
                if chat.operator_id is not None
            )
        )


def detached_repositories() -> Repositories:
    return Repositories(DetachedRepository(), DetachedRepository(), DetachedChatRepository())
