from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Any, TypeVar

from .exceptions import ValidationError
from .models import Operator, Person, User, validate_integer
from .repositories import Repositories

P = TypeVar("P", bound=Person)
EDITABLE_FIELDS = frozenset({"full_name", "city", "birth_date", "position", "experience_years"})


def parse_birth_date(value: date | str) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValidationError("Дата рождения должна иметь формат YYYY-MM-DD")


class ProfileService:
    def __init__(
        self,
        repositories: Repositories,
        on_operator_registered: Callable[[], None],
        max_active_chats: int = 1,
    ) -> None:
        validate_integer(max_active_chats, "max_active_chats", 1)
        self._repositories = repositories
        self._on_operator_registered = on_operator_registered
        self.max_active_chats = max_active_chats

    def register_operator(
        self,
        full_name: str,
        city: str,
        birth_date: date | str,
        position: str,
        experience_years: int,
        max_active_chats: int | None = None,
    ) -> Operator:
        operator = Operator(
            id=self._repositories.operators.next_id(),
            full_name=full_name,
            city=city,
            birth_date=parse_birth_date(birth_date),
            position=position,
            experience_years=experience_years,
            max_active_chats=self.max_active_chats
            if max_active_chats is None
            else max_active_chats,
        )
        self._repositories.operators.add(operator)
        self._on_operator_registered()
        return operator

    def register_user(
        self,
        full_name: str,
        city: str,
        birth_date: date | str,
        position: str,
        experience_years: int,
    ) -> User:
        user = User(
            id=self._repositories.users.next_id(),
            full_name=full_name,
            city=city,
            birth_date=parse_birth_date(birth_date),
            position=position,
            experience_years=experience_years,
        )
        self._repositories.users.add(user)
        return user

    @staticmethod
    def _updated(person: P, fields: dict[str, Any]) -> P:
        unknown = fields.keys() - EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"Нельзя изменить поля: {', '.join(sorted(unknown))}")
        if "birth_date" in fields:
            fields["birth_date"] = parse_birth_date(fields["birth_date"])
        return replace(person, **fields)

    def update_operator(self, operator_id: int, **fields: Any) -> Operator:
        operator = self._updated(self._repositories.operators.get(operator_id), fields)
        self._repositories.operators.save(operator)
        return operator

    def update_user(self, user_id: int, **fields: Any) -> User:
        user = self._updated(self._repositories.users.get(user_id), fields)
        self._repositories.users.save(user)
        return user
