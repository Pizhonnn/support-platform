import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from support_platform import (
    Application,
    ChatStateError,
    Exporter,
    JsonStateStore,
    PlatformError,
    generator,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Примеры выгрузок платформы поддержки")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--state", type=Path, default=ROOT / "data" / "platform_state.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "exports")
    parser.add_argument(
        "--demo", action="store_true", help="Обновить профили и создать новое обращение"
    )
    return parser.parse_args()


def demo_actions(app: Application, rng: random.Random) -> None:
    operators = app.queries.all_operators()
    users = app.queries.all_users()
    if operators:
        operator = operators[0]
        updated = app.profiles.update_operator(
            operator.id,
            position="Старший оператор поддержки",
            experience_years=operator.experience_years + 1,
        )
        print(f"Оператор #{updated.id}: {updated.position}, стаж {updated.experience_years}")
    if not users:
        return
    user = app.profiles.update_user(users[0].id, city="Сочи")
    print(f"Пользователь #{user.id}: город {user.city}")
    chat = app.platform.create_chat(
        rng.choice(users).id, "Здравствуйте! Не работает поиск по каталогу."
    )
    print(f"Создан чат #{chat.id}, статус {chat.status.value}")
    if chat.operator_id is not None:
        app.platform.operator_reply(
            chat.id, "Добрый день! Уже чиню, обновите страницу через минуту."
        )
        app.platform.close_chat(chat.id)
        app.platform.rate_chat(chat.id, 5)
        try:
            app.platform.rate_chat(chat.id, 3)
        except ChatStateError as exc:
            print(f"Повторная оценка отклонена: {exc}")


def main() -> None:
    args = parse_args()
    store = JsonStateStore()
    rng = random.Random(args.seed)
    try:
        existed = args.state.exists()
        app = (
            store.load(args.state, rng=rng)
            if existed
            else generator.generate_platform(seed=args.seed)
        )
        if args.demo:
            demo_actions(app, rng)
        exporter = Exporter(app.queries, args.output_dir, verbose=args.verbose, quiet=args.quiet)
        if args.all:
            exporter.export_everything()
        else:
            exporter.export_all_chats()
            operators = app.queries.all_operators()
            if operators:
                exporter.export_operator_chats(rng.choice(operators).id)
            user_ids = sorted({chat.user_id for chat in app.queries.all_chats()})
            if user_ids:
                exporter.export_user_chats(rng.choice(user_ids))
            exporter.export_operators()
            exporter.export_users()
        if args.demo or not existed:
            store.save(app, args.state)
        if not args.quiet:
            print(f"Файлы выгрузок: {args.output_dir}")
    except (PlatformError, OSError) as exc:
        raise SystemExit(f"Ошибка: {exc}") from None


if __name__ == "__main__":
    main()
