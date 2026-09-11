from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from .exceptions import ChatStateError, ValidationError

CSAT_MIN = 1
CSAT_MAX = 5


class ChatStatus(StrEnum):
    WAITING = "waiting"
    OPEN = "open"
    CLOSED = "closed"


class SenderType(StrEnum):
    USER = "user"
    OPERATOR = "operator"


def validate_integer(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"{name}: ожидается целое число не меньше {minimum}")


def validate_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name}: ожидается непустая строка")


def validate_datetime(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is not None:
        raise ValidationError("Ожидается datetime без часового пояса")


@dataclass(frozen=True, slots=True)
class Person:
    id: int
    full_name: str
    city: str
    birth_date: date
    position: str
    experience_years: int

    def __post_init__(self) -> None:
        validate_integer(self.id, "id", 1)
        for name in ("full_name", "city", "position"):
            validate_text(getattr(self, name), name)
        if type(self.birth_date) is not date or self.birth_date > date.today():
            raise ValidationError("Дата рождения должна быть датой не позднее сегодняшней")
        validate_integer(self.experience_years, "experience_years")

    @property
    def age(self) -> int:
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )


@dataclass(frozen=True, slots=True)
class Operator(Person):
    max_active_chats: int = 1

    def __post_init__(self) -> None:
        Person.__post_init__(self)
        validate_integer(self.max_active_chats, "max_active_chats", 1)


@dataclass(frozen=True, slots=True)
class User(Person):
    pass


@dataclass(frozen=True, slots=True)
class Message:
    sender_type: SenderType
    sender_id: int
    text: str
    sent_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.sender_type, SenderType):
            raise ValidationError("Неизвестный тип отправителя")
        validate_integer(self.sender_id, "sender_id", 1)
        validate_text(self.text, "text")
        validate_datetime(self.sent_at)


@dataclass(slots=True)
class Chat:
    id: int
    user_id: int
    created_at: datetime
    operator_id: int | None = None
    status: ChatStatus = ChatStatus.WAITING
    messages: list[Message] = field(default_factory=list)
    closed_at: datetime | None = None
    csat: int | None = None

    def __post_init__(self) -> None:
        validate_integer(self.id, "id", 1)
        validate_integer(self.user_id, "user_id", 1)
        validate_datetime(self.created_at)
        if not isinstance(self.status, ChatStatus):
            raise ValidationError("Неизвестный статус чата")
        if self.operator_id is not None:
            validate_integer(self.operator_id, "operator_id", 1)
        if (self.status == ChatStatus.WAITING) != (self.operator_id is None):
            raise ValidationError("Назначение оператора не соответствует статусу чата")
        if self.is_closed != (self.closed_at is not None):
            raise ValidationError("Время закрытия не соответствует статусу чата")
        previous = self.created_at
        for message in self.messages:
            self._check_sender(message)
            if message.sent_at < previous:
                raise ValidationError("Сообщения должны идти в хронологическом порядке")
            previous = message.sent_at
        if self.closed_at is not None:
            self._check_time(self.closed_at)
        if self.csat is not None:
            if not self.is_closed:
                raise ValidationError("Оценка допустима только у закрытого чата")
            self._check_score(self.csat)

    @property
    def is_closed(self) -> bool:
        return self.status == ChatStatus.CLOSED

    @property
    def last_message_at(self) -> datetime | None:
        return self.messages[-1].sent_at if self.messages else None

    def _check_time(self, at: datetime) -> None:
        validate_datetime(at)
        if at < (self.last_message_at or self.created_at):
            raise ValidationError(f"Время события раньше последнего события чата #{self.id}")

    def _check_sender(self, message: Message) -> None:
        expected = self.user_id if message.sender_type == SenderType.USER else self.operator_id
        if message.sender_id != expected:
            raise ValidationError("Отправитель не является участником чата")

    @staticmethod
    def _check_score(csat: int) -> None:
        if type(csat) is not int or not CSAT_MIN <= csat <= CSAT_MAX:
            raise ValidationError(f"csat должен быть целым числом от {CSAT_MIN} до {CSAT_MAX}")

    def assign(self, operator_id: int) -> None:
        if self.status != ChatStatus.WAITING:
            raise ChatStateError("Назначить оператора можно только ожидающему чату")
        validate_integer(operator_id, "operator_id", 1)
        self.operator_id = operator_id
        self.status = ChatStatus.OPEN

    def add_message(self, message: Message) -> None:
        if self.is_closed:
            raise ChatStateError(f"Чат #{self.id} закрыт, писать в него нельзя")
        if message.sender_type == SenderType.OPERATOR and self.status != ChatStatus.OPEN:
            raise ChatStateError("Оператор может отвечать только в открытый чат")
        self._check_sender(message)
        self._check_time(message.sent_at)
        self.messages.append(message)

    def close(self, at: datetime) -> None:
        if self.status != ChatStatus.OPEN:
            raise ChatStateError("Закрыть можно только открытый чат")
        self._check_time(at)
        self.status = ChatStatus.CLOSED
        self.closed_at = at

    def rate(self, csat: int) -> None:
        if not self.is_closed:
            raise ChatStateError("Оценить можно только закрытый чат")
        if self.csat is not None:
            raise ChatStateError(f"Чат #{self.id} уже оценён ({self.csat})")
        self._check_score(csat)
        self.csat = csat
