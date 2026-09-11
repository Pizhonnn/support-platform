import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from support_platform import Application, Chat, ChatStatus, JsonStateStore, PlatformError, generator


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Ожидается положительное целое число")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("Ожидается неотрицательное целое число")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Генерация чатов платформы поддержки")
    parser.add_argument("--operators", type=positive_int, default=10)
    parser.add_argument("--users", type=positive_int, default=40)
    parser.add_argument("--chats", type=positive_int, default=120)
    parser.add_argument("--max-active", type=positive_int, default=3)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--start", type=datetime.fromisoformat, help="Начало симуляции в ISO-формате"
    )
    parser.add_argument("--show", type=nonnegative_int, default=3)
    parser.add_argument("--state", type=Path, default=ROOT / "data" / "platform_state.json")
    args = parser.parse_args()
    if args.chats < 100:
        parser.error("Нужно не меньше 100 чатов")
    return args


def print_chat(app: Application, chat: Chat) -> None:
    user = app.queries.get_user(chat.user_id)
    operator = (
        app.queries.get_operator(chat.operator_id).full_name
        if chat.operator_id is not None
        else "не назначен"
    )
    print(f"Чат #{chat.id} [{chat.status.value}] {user.full_name} | оператор: {operator}")
    for message in chat.messages:
        who = "Пользователь" if message.sender_type.value == "user" else "Оператор"
        print(f"    {message.sent_at:%Y-%m-%d %H:%M} {who:<12} {message.text}")
    print(f"    Закрыт: {chat.closed_at}, csat: {chat.csat}")
    print()


def main() -> None:
    args = parse_args()
    try:
        app = generator.generate_platform(
            operators=args.operators,
            users=args.users,
            chats=args.chats,
            max_active_chats=args.max_active,
            seed=args.seed,
            start=args.start,
        )
        stats = app.queries.stats()
        print("СГЕНЕРИРОВАНО")
        print(
            f"Операторов: {stats['operators']}, пользователей: {stats['users']}, "
            f"чатов: {stats['chats_total']}"
        )
        print(f"Статусы: {stats['chats_by_status']}")
        print(f"Закрыто без оценки: {stats['chats_closed_without_csat']}")
        print(f"Распределение csat: {stats['csat_distribution']}")
        print(f"Средний csat: {stats['avg_csat']}")
        print(f"Ожидают оператора: {len(stats['waiting_queue'])}")
        for status in ChatStatus:
            for chat in app.queries.chats_by_status(status)[: args.show]:
                print_chat(app, chat)
        path = JsonStateStore().save(app, args.state)
        print(f"Состояние платформы сохранено: {path}")
    except (PlatformError, OSError) as exc:
        raise SystemExit(f"Ошибка: {exc}") from None


if __name__ == "__main__":
    main()
