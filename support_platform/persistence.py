import json
from pathlib import Path
from random import Random
from typing import Any

from .application import Application, create_application
from .exceptions import PlatformError, ValidationError
from .json_io import write_json
from .models import Chat, ChatStatus, SenderType, validate_integer
from .serialization import (
    chat_from_record,
    chat_record,
    operator_from_record,
    operator_record,
    person_record,
    user_from_record,
)


class JsonStateStore:
    @staticmethod
    def to_dict(app: Application) -> dict[str, Any]:
        queries = app.queries
        active = queries.active_chat_ids()
        return {
            "schema_version": 1,
            "max_active_chats": app.profiles.max_active_chats,
            "waiting_queue": queries.waiting_ids(),
            "operators": [
                operator_record(operator, active.get(operator.id, []))
                for operator in queries.all_operators()
            ],
            "users": [person_record(user) for user in queries.all_users()],
            "chats": [chat_record(chat) for chat in queries.all_chats()],
        }

    @staticmethod
    def from_dict(data: dict[str, Any], rng: Random | None = None) -> Application:
        try:
            return JsonStateStore._restore(data, rng)
        except (KeyError, TypeError, ValueError, AttributeError, PlatformError) as exc:
            raise ValidationError(f"Некорректное состояние платформы: {exc}") from exc

    @staticmethod
    def _restore(data: dict[str, Any], rng: Random | None) -> Application:
        version = data.get("schema_version", 1)
        if type(version) is not int or version != 1:
            raise ValidationError(f"Неизвестная версия состояния: {version}")
        app = create_application(max_active_chats=data.get("max_active_chats", 1), rng=rng)
        repositories = app.repositories
        for item in data["operators"]:
            repositories.operators.add(operator_from_record(item))
        for item in data["users"]:
            repositories.users.add(user_from_record(item))
        waiting: dict[int, Chat] = {}
        for item in data["chats"]:
            chat = chat_from_record(item)
            repositories.users.get(chat.user_id)
            if chat.operator_id is not None:
                repositories.operators.get(chat.operator_id)
            if (
                not chat.messages
                or chat.messages[0].sent_at != chat.created_at
                or chat.messages[0].sender_type != SenderType.USER
            ):
                raise ValidationError(f"У чата #{chat.id} отсутствует начальное сообщение")
            if chat.id in waiting:
                raise ValidationError(f"Повторяющийся id чата: {chat.id}")
            if chat.status == ChatStatus.WAITING:
                waiting[chat.id] = chat
            else:
                repositories.chats.add(chat)
        queue = data.get("waiting_queue", list(waiting))
        if not isinstance(queue, list):
            raise ValidationError("Очередь должна быть списком id")
        for chat_id in queue:
            validate_integer(chat_id, "waiting_queue id", 1)
        if len(queue) != len(waiting) or set(queue) != waiting.keys():
            raise ValidationError("Очередь не соответствует ожидающим чатам")
        for chat_id in queue:
            repositories.chats.add(waiting[chat_id])
        active = repositories.chats.active_counts()
        for operator in repositories.operators.list():
            if active.get(operator.id, 0) > operator.max_active_chats:
                raise ValidationError(f"Превышена нагрузка оператора #{operator.id}")
        app.platform.dispatch_queue()
        return app

    def save(self, app: Application, path: str | Path) -> Path:
        return write_json(path, self.to_dict(app))

    def load(self, path: str | Path, rng: Random | None = None) -> Application:
        try:
            with Path(path).open(encoding="utf-8") as stream:
                data = json.load(stream)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ValidationError(f"Некорректный JSON в {path}") from exc
        return self.from_dict(data, rng=rng)
