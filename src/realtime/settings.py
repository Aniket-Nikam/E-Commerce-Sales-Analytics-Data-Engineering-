from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.config import REALTIME_DB_PATH


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RealtimeSettings:
    rabbitmq_url: str
    queue_name: str
    db_path: Path
    embed_consumer: bool

    @classmethod
    def from_env(cls) -> "RealtimeSettings":
        return cls(
            rabbitmq_url=os.getenv(
                "RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"
            ),
            queue_name=os.getenv("RABBITMQ_QUEUE", "ecommerce.order.events"),
            db_path=Path(os.getenv("REALTIME_DB_PATH", str(REALTIME_DB_PATH))),
            embed_consumer=_env_bool("REALTIME_EMBED_CONSUMER", True),
        )

