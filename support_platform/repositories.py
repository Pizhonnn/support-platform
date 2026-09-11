from dataclasses import dataclass
from typing import Protocol, TypeVar

from .models import Chat, ChatStatus, Operator, User

T = TypeVar("T", Chat, Operator, User)


class Repository(Protocol[T]):
    def next_id(self) -> int: ...

    def add(self, entity: T) -> None: ...

    def get(self, entity_id: int) -> T: ...

    def save(self, entity: T) -> None: ...

    def list(self) -> list[T]: ...


class ChatRepository(Repository[Chat], Protocol):
    def by_user(self, user_id: int) -> list[Chat]: ...

    def by_operator(self, operator_id: int) -> list[Chat]: ...

    def by_status(self, status: ChatStatus) -> list[Chat]: ...

    def next_waiting(self) -> Chat | None: ...

    def waiting_ids(self) -> list[int]: ...

    def active_counts(self) -> dict[int, int]: ...


@dataclass(frozen=True, slots=True)
class Repositories:
    operators: Repository[Operator]
    users: Repository[User]
    chats: ChatRepository
