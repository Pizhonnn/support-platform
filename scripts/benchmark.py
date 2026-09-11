import argparse
import json
import platform
import statistics
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from support_platform import generator


def main() -> None:
    parser = argparse.ArgumentParser(description="Измерение генерации, статистики и выборок")
    parser.add_argument("--chats", type=int, default=10000)
    parser.add_argument("--iterations", type=int, default=7)
    args = parser.parse_args()
    if args.chats < 1 or args.iterations < 1:
        parser.error("Количество чатов и итераций должно быть положительным")
    started = perf_counter()
    app = generator.generate_platform(
        operators=100, users=1000, chats=args.chats, seed=42, start=datetime(2026, 1, 1)
    )
    generation = perf_counter() - started
    app.queries.stats()
    stats_times = []
    query_times = []
    for _ in range(args.iterations):
        started = perf_counter()
        app.queries.stats()
        stats_times.append(perf_counter() - started)
        started = perf_counter()
        for user in app.queries.all_users():
            app.queries.chats_by_user(user.id)
        query_times.append(perf_counter() - started)
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "chats": args.chats,
                "iterations": args.iterations,
                "generation_seconds": round(generation, 6),
                "stats_median_seconds": round(statistics.median(stats_times), 6),
                "all_user_queries_median_seconds": round(statistics.median(query_times), 6),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
