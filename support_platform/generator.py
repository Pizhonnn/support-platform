from __future__ import annotations

import random
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

from .application import Application, create_application
from .exceptions import ValidationError
from .models import (
    CSAT_MAX,
    CSAT_MIN,
    Chat,
    ChatStatus,
    Operator,
    User,
    validate_datetime,
    validate_integer,
)

NAMES = {
    "male": {
        "first": [
            "Александр",
            "Дмитрий",
            "Максим",
            "Иван",
            "Артём",
            "Никита",
            "Михаил",
            "Егор",
            "Андрей",
            "Сергей",
            "Алексей",
            "Павел",
            "Роман",
            "Кирилл",
        ],
        "patronymic": [
            "Александрович",
            "Дмитриевич",
            "Сергеевич",
            "Иванович",
            "Андреевич",
            "Алексеевич",
            "Владимирович",
            "Николаевич",
            "Петрович",
            "Олегович",
        ],
        "last": [
            "Иванов",
            "Смирнов",
            "Кузнецов",
            "Попов",
            "Васильев",
            "Петров",
            "Соколов",
            "Михайлов",
            "Новиков",
            "Фёдоров",
            "Морозов",
            "Волков",
            "Лебедев",
            "Козлов",
        ],
    },
    "female": {
        "first": [
            "Анна",
            "Мария",
            "Елена",
            "Ольга",
            "Наталья",
            "Екатерина",
            "Татьяна",
            "Ирина",
            "Дарья",
            "Светлана",
            "Юлия",
            "Полина",
            "Алина",
            "Ксения",
        ],
        "patronymic": [
            "Александровна",
            "Дмитриевна",
            "Сергеевна",
            "Ивановна",
            "Андреевна",
            "Алексеевна",
            "Владимировна",
            "Николаевна",
            "Петровна",
            "Олеговна",
        ],
        "last": [
            "Иванова",
            "Смирнова",
            "Кузнецова",
            "Попова",
            "Васильева",
            "Петрова",
            "Соколова",
            "Михайлова",
            "Новикова",
            "Фёдорова",
            "Морозова",
            "Волкова",
            "Лебедева",
            "Козлова",
        ],
    },
}

CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Самара",
    "Омск",
    "Ростов-на-Дону",
    "Уфа",
    "Красноярск",
    "Воронеж",
    "Пермь",
    "Волгоград",
    "Краснодар",
    "Тюмень",
    "Калининград",
]

OPERATOR_POSITIONS = [
    "Стажёр поддержки",
    "Оператор поддержки",
    "Оператор поддержки",
    "Старший оператор поддержки",
    "Ведущий специалист поддержки",
]

USER_POSITIONS = [
    "Менеджер по продажам",
    "Бухгалтер",
    "Инженер",
    "Студент",
    "Врач",
    "Учитель",
    "Дизайнер",
    "Программист",
    "Юрист",
    "Предприниматель",
    "Водитель",
    "Маркетолог",
    "Аналитик",
    "Администратор",
    "Логист",
    "Пенсионер",
]

USER_OPENING = [
    "Здравствуйте! Не могу войти в личный кабинет, пишет «неверный пароль».",
    "Добрый день. Списали деньги дважды за одну покупку, помогите разобраться.",
    "Привет! Заказ №{n} уже неделю в статусе «в пути», где он?",
    "Здравствуйте, не приходит смс с кодом подтверждения.",
    "Добрый вечер! Хочу вернуть товар, как оформить возврат?",
    "Приложение вылетает при открытии раздела «Платежи».",
    "Не могу привязать новую карту, ошибка «операция отклонена».",
    "Здравствуйте! Как изменить номер телефона в профиле?",
    "Промокод {code} не применяется в корзине, хотя срок действия не истёк.",
    "Добрый день, не могу скачать чек по заказу №{n}.",
]

OPERATOR_GREETING = [
    "Здравствуйте! Меня зовут {name}, я помогу вам. Уточните, пожалуйста, детали.",
    "Добрый день! Спасибо за обращение, уже разбираюсь с вашим вопросом.",
    "Здравствуйте! Проверяю информацию по вашему запросу, минуту.",
    "Приветствую! Подскажите, пожалуйста, когда впервые возникла проблема?",
]

USER_FOLLOWUP = [
    "Проблема появилась вчера вечером, до этого всё работало.",
    "Пробовал(а) перезапустить приложение – не помогло.",
    "Да, номер телефона тот же, что и при регистрации.",
    "Прикладываю скриншот ошибки: {code}.",
    "Оплачивал(а) картой, платёж прошёл дважды.",
]

OPERATOR_SOLUTION = [
    "Спасибо! Я сбросил(а) настройки на нашей стороне, попробуйте ещё раз.",
    "Вижу проблему. Оформил(а) возврат средств, деньги вернутся в течение 3–5 дней.",
    "Передал(а) запрос в техническую команду, обновление придёт в ближайшие часы.",
    "Отправил(а) вам новую ссылку для подтверждения на почту.",
    "Заказ задержался на сортировочном центре, доставка ожидается завтра.",
]

USER_THANKS = [
    "Спасибо большое, всё заработало!",
    "Отлично, спасибо за помощь.",
    "Понял(а), буду ждать. Спасибо!",
    "Хорошо, спасибо.",
]

OPERATOR_CLOSING = [
    "Рад(а) помочь! Закрываю обращение, хорошего дня.",
    "Спасибо за обращение! Если вопрос повторится – пишите.",
    "Обращение закрыто. Будем благодарны за оценку нашей работы!",
]


def random_birth_date(
    rng: random.Random,
    min_age: int = 18,
    max_age: int = 65,
    today: date | None = None,
) -> date:
    validate_integer(min_age, "min_age")
    validate_integer(max_age, "max_age", min_age)
    today = date.today() if today is None else today
    if max_age >= today.year - 1:
        raise ValidationError("Диапазон возраста выходит за пределы календаря")
    youngest_year = today.year - min_age
    oldest_year = today.year - max_age - 1
    youngest = today.replace(
        year=youngest_year, day=min(today.day, monthrange(youngest_year, today.month)[1])
    )
    oldest = today.replace(
        year=oldest_year, day=min(today.day, monthrange(oldest_year, today.month)[1])
    )
    return oldest + timedelta(days=rng.randint(1, (youngest - oldest).days))


def random_person_data(
    rng: random.Random, positions: list[str], today: date | None = None
) -> dict[str, Any]:
    today = date.today() if today is None else today
    names = NAMES[rng.choice(list(NAMES))]
    full_name = " ".join(rng.choice(names[key]) for key in ("last", "first", "patronymic"))
    birth_date = random_birth_date(rng, today=today)
    age = (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )
    return {
        "full_name": full_name,
        "city": rng.choice(CITIES),
        "birth_date": birth_date,
        "position": rng.choice(positions),
        "experience_years": rng.randint(0, min(age - 18, 40)),
    }


def generate_operators(
    app: Application, count: int, rng: random.Random | None = None, today: date | None = None
) -> list[Operator]:
    validate_integer(count, "operators")
    rng = random.Random() if rng is None else rng
    return [
        app.profiles.register_operator(**random_person_data(rng, OPERATOR_POSITIONS, today))
        for _ in range(count)
    ]


def generate_users(
    app: Application, count: int, rng: random.Random | None = None, today: date | None = None
) -> list[User]:
    validate_integer(count, "users")
    rng = random.Random() if rng is None else rng
    return [
        app.profiles.register_user(**random_person_data(rng, USER_POSITIONS, today))
        for _ in range(count)
    ]


def _fill(template: str, rng: random.Random, operator_name: str = "") -> str:
    parts = operator_name.split()
    return template.format(
        n=rng.randint(10000, 99999),
        code=f"ERR-{rng.randint(100, 999)}",
        name=parts[min(1, len(parts) - 1)] if parts else "оператор",
    )


def generate_chats(
    app: Application,
    count: int,
    start: datetime | None = None,
    close_probability: float = 0.8,
    rate_probability: float = 0.8,
    rng: random.Random | None = None,
) -> list[Chat]:
    validate_integer(count, "chats")
    for probability in (close_probability, rate_probability):
        if type(probability) not in (int, float) or not 0 <= probability <= 1:
            raise ValidationError("Вероятность должна быть числом от 0 до 1")
    rng = random.Random() if rng is None else rng
    cursor = start if start is not None else datetime.now() - timedelta(days=30)
    validate_datetime(cursor)
    cursor = cursor.replace(second=0, microsecond=0)
    user_ids = [user.id for user in app.queries.all_users()]
    if count and not user_ids:
        raise ValidationError("Сначала зарегистрируйте пользователей")
    platform = app.platform
    created: list[Chat] = []
    for _ in range(count):
        cursor += timedelta(minutes=rng.randint(1, 120))
        chat = platform.create_chat(
            rng.choice(user_ids), _fill(rng.choice(USER_OPENING), rng), at=cursor
        )
        created.append(chat)
        if chat.status != ChatStatus.OPEN or chat.operator_id is None:
            continue
        operator_name = app.queries.get_operator(chat.operator_id).full_name
        moment = cursor + timedelta(minutes=rng.randint(1, 15))
        platform.operator_reply(
            chat.id, _fill(rng.choice(OPERATOR_GREETING), rng, operator_name), at=moment
        )
        for _ in range(rng.randint(0, 2)):
            moment += timedelta(minutes=rng.randint(1, 20))
            platform.user_reply(chat.id, _fill(rng.choice(USER_FOLLOWUP), rng), at=moment)
            moment += timedelta(minutes=rng.randint(1, 20))
            platform.operator_reply(chat.id, _fill(rng.choice(OPERATOR_SOLUTION), rng), at=moment)
        if rng.random() < close_probability:
            if rng.random() < 0.7:
                moment += timedelta(minutes=rng.randint(1, 30))
                platform.user_reply(chat.id, rng.choice(USER_THANKS), at=moment)
            moment += timedelta(minutes=rng.randint(1, 10))
            platform.operator_reply(chat.id, rng.choice(OPERATOR_CLOSING), at=moment)
            platform.close_chat(chat.id, at=moment)
            if rng.random() < rate_probability:
                platform.rate_chat(chat.id, rng.randint(CSAT_MIN, CSAT_MAX))
        cursor = moment
    return [app.queries.get_chat(chat.id) for chat in created]


def generate_platform(
    operators: int = 10,
    users: int = 40,
    chats: int = 120,
    max_active_chats: int = 3,
    seed: int | None = None,
    start: datetime | None = None,
) -> Application:
    validate_integer(operators, "operators")
    validate_integer(users, "users")
    validate_integer(chats, "chats")
    if chats and not users:
        raise ValidationError("Для генерации чатов нужен хотя бы один пользователь")
    start = start if start is not None else datetime.now() - timedelta(days=30)
    validate_datetime(start)
    rng = random.Random(seed)
    app = create_application(max_active_chats=max_active_chats, rng=rng)
    generate_operators(app, operators, rng, start.date())
    generate_users(app, users, rng, start.date())
    generate_chats(app, chats, start=start, rng=rng)
    return app
