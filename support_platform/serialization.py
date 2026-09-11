from datetime import datetime
from typing import Any

from .models import Chat, ChatStatus, Message, Operator, Person, SenderType, User
from .profiles import parse_birth_date

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def person_record(person: Person) -> dict[str, Any]:
    return {
        "id": person.id,
        "full_name": person.full_name,
        "city": person.city,
        "birth_date": person.birth_date.isoformat(),
        "age": person.age,
        "position": person.position,
        "experience_years": person.experience_years,
    }


def operator_record(operator: Operator, active_chat_ids: list[int]) -> dict[str, Any]:
    return {
        **person_record(operator),
        "max_active_chats": operator.max_active_chats,
        "active_chat_ids": list(active_chat_ids),
        "is_free": len(active_chat_ids) < operator.max_active_chats,
    }


def message_record(message: Message) -> dict[str, Any]:
    return {
        "sender_type": message.sender_type.value,
        "sender_id": message.sender_id,
        "text": message.text,
        "sent_at": message.sent_at.strftime(DATETIME_FMT),
    }


def chat_record(chat: Chat) -> dict[str, Any]:
    return {
        "id": chat.id,
        "user_id": chat.user_id,
        "operator_id": chat.operator_id,
        "status": chat.status.value,
        "created_at": chat.created_at.strftime(DATETIME_FMT),
        "closed_at": chat.closed_at.strftime(DATETIME_FMT) if chat.closed_at is not None else None,
        "csat": chat.csat,
        "messages": [message_record(message) for message in chat.messages],
    }


def _profile_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": data["id"],
        "full_name": data["full_name"],
        "city": data["city"],
        "birth_date": parse_birth_date(data["birth_date"]),
        "position": data["position"],
        "experience_years": data["experience_years"],
    }


def user_from_record(data: dict[str, Any]) -> User:
    return User(**_profile_fields(data))


def operator_from_record(data: dict[str, Any]) -> Operator:
    return Operator(**_profile_fields(data), max_active_chats=data.get("max_active_chats", 1))


def message_from_record(data: dict[str, Any]) -> Message:
    return Message(
        sender_type=SenderType(data["sender_type"]),
        sender_id=data["sender_id"],
        text=data["text"],
        sent_at=datetime.strptime(data["sent_at"], DATETIME_FMT),
    )


def chat_from_record(data: dict[str, Any]) -> Chat:
    return Chat(
        id=data["id"],
        user_id=data["user_id"],
        operator_id=data.get("operator_id"),
        status=ChatStatus(data["status"]),
        created_at=datetime.strptime(data["created_at"], DATETIME_FMT),
        closed_at=datetime.strptime(data["closed_at"], DATETIME_FMT)
        if data.get("closed_at") is not None
        else None,
        csat=data.get("csat"),
        messages=[message_from_record(message) for message in data["messages"]],
    )
