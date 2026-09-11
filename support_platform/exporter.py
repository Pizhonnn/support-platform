import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .json_io import write_json
from .models import Chat
from .queries import PlatformQueries
from .serialization import DATETIME_FMT, chat_record, operator_record, person_record


class Exporter:
    def __init__(
        self,
        queries: PlatformQueries,
        output_dir: str | Path = "exports",
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        self.queries = queries
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.quiet = quiet

    def _chat_record(self, chat: Chat) -> dict[str, Any]:
        return {
            **chat_record(chat),
            "user_name": self.queries.get_user(chat.user_id).full_name,
            "operator_name": self.queries.get_operator(chat.operator_id).full_name
            if chat.operator_id is not None
            else None,
        }

    def _write(
        self,
        kind: str,
        filename: str,
        items: list[dict[str, Any]],
        title: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "export_type": kind,
            "exported_at": datetime.now().strftime(DATETIME_FMT),
            "count": len(items),
            **(extra or {}),
            "items": items,
        }
        path = write_json(self.output_dir / filename, payload)
        if not self.quiet:
            print("=" * 80)
            print(title)
            print(f"Записей: {len(items)} | файл: {path}")
            for item in items:
                print(self._format_line(kind, item))
            if self.verbose:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            print()
        return payload

    @staticmethod
    def _format_line(kind: str, item: dict[str, Any]) -> str:
        if kind.startswith("chats"):
            operator = item["operator_name"] or "не назначен"
            csat = item["csat"] if item["csat"] is not None else "—"
            return (
                f"чат #{item['id']:<4} {item['status']:<8} создан {item['created_at']} "
                f"пользователь: {item['user_name']} | оператор: {operator} "
                f"сообщений: {len(item['messages'])} | csat: {csat}"
            )
        return (
            f"#{item['id']:<4} {item['full_name']:<32} {item['city']:<18} "
            f"{item['birth_date']} ({item['age']} лет) | {item['position']} | "
            f"стаж: {item['experience_years']} лет"
        )

    def export_all_chats(self, filename: str = "all_chats.json") -> dict[str, Any]:
        items = [self._chat_record(chat) for chat in self.queries.all_chats()]
        return self._write("chats_all", filename, items, "ВЫГРУЗКА: все чаты")

    def export_operator_chats(
        self, operator_id: int, filename: str | None = None
    ) -> dict[str, Any]:
        operator = self.queries.get_operator(operator_id)
        chats = self.queries.chats_by_operator(operator_id)
        active = [chat.id for chat in chats if not chat.is_closed]
        return self._write(
            "chats_by_operator",
            filename or f"chats_operator_{operator_id}.json",
            [self._chat_record(chat) for chat in chats],
            f"ВЫГРУЗКА: чаты оператора {operator.full_name}",
            extra={"operator": operator_record(operator, active)},
        )

    def export_user_chats(self, user_id: int, filename: str | None = None) -> dict[str, Any]:
        user = self.queries.get_user(user_id)
        return self._write(
            "chats_by_user",
            filename or f"chats_user_{user_id}.json",
            [self._chat_record(chat) for chat in self.queries.chats_by_user(user_id)],
            f"ВЫГРУЗКА: чаты пользователя {user.full_name}",
            extra={"user": person_record(user)},
        )

    def export_operators(self, filename: str = "operators.json") -> dict[str, Any]:
        stats = self.queries.operator_stats()
        active = self.queries.active_chat_ids()
        items = [
            {**operator_record(operator, active.get(operator.id, [])), **stats[operator.id]}
            for operator in self.queries.all_operators()
        ]
        return self._write("operators", filename, items, "ВЫГРУЗКА: операторы")

    def export_users(self, filename: str = "users.json") -> dict[str, Any]:
        counts = self.queries.user_chat_counts()
        items = [
            {**person_record(user), "chats_total": counts.get(user.id, 0)}
            for user in self.queries.all_users()
        ]
        return self._write("users", filename, items, "ВЫГРУЗКА: пользователи")

    def export_everything(self) -> None:
        self.export_all_chats()
        for operator in self.queries.all_operators():
            self.export_operator_chats(operator.id)
        for user in self.queries.all_users():
            self.export_user_chats(user.id)
        self.export_operators()
        self.export_users()
