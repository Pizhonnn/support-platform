from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from random import Random

from .core import SupportPlatform
from .profiles import ProfileService
from .queries import PlatformQueries
from .repositories import Repositories
from .storage import InMemoryDatabase, memory_repositories


@dataclass(frozen=True, slots=True)
class Application:
    repositories: Repositories
    profiles: ProfileService
    platform: SupportPlatform
    queries: PlatformQueries


def create_application(
    repositories: Repositories | None = None,
    *,
    max_active_chats: int = 1,
    rng: Random | None = None,
    clock: Callable[[], datetime] = datetime.now,
) -> Application:
    if repositories is None:
        repositories = memory_repositories(InMemoryDatabase())
    platform = SupportPlatform(repositories, rng=rng, clock=clock)
    return Application(
        repositories=repositories,
        profiles=ProfileService(repositories, platform.dispatch_queue, max_active_chats),
        platform=platform,
        queries=PlatformQueries(repositories),
    )
