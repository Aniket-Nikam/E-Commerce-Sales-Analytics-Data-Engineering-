from __future__ import annotations

import json
import logging
import signal
import threading
import time
from datetime import datetime, timezone

import pika
from pydantic import ValidationError

from src.config import LOGS_DIR, ensure_directories

from .models import OrderEvent
from .settings import RealtimeSettings
from .store import RealtimeStore

LOGGER = logging.getLogger("realtime-consumer")


def process_message(body: bytes, store: RealtimeStore) -> str:
    event = OrderEvent.model_validate_json(body)
    return "inserted" if store.insert(event) else "duplicate"


def record_dead_letter(body: bytes, error: Exception) -> None:
    ensure_directories()
    entry = {
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "error": str(error),
        "payload": body.decode("utf-8", errors="replace"),
    }
    with (LOGS_DIR / "realtime_dead_letters.ndjson").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry) + "\n")


class ConsumerWorker:
    def __init__(self, settings: RealtimeSettings, store: RealtimeStore):
        self.settings = settings
        self.store = store
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._connection: pika.BlockingConnection | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run, name="rabbitmq-consumer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._connection and self._connection.is_open:
            self._connection.add_callback_threadsafe(self._connection.close)
        if self._thread:
            self._thread.join(timeout=10)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._consume_once()
            except Exception as error:
                if not self._stop.is_set():
                    LOGGER.warning("Consumer reconnecting after error: %s", error)
                    self._stop.wait(2)

    def _consume_once(self) -> None:
        parameters = pika.URLParameters(self.settings.rabbitmq_url)
        parameters.heartbeat = 30
        parameters.blocked_connection_timeout = 30
        self._connection = pika.BlockingConnection(parameters)
        channel = self._connection.channel()
        channel.queue_declare(queue=self.settings.queue_name, durable=True)
        batch_size = 25
        batch_seconds = 2.0
        channel.basic_qos(prefetch_count=batch_size)
        pending: list[tuple[object, object, OrderEvent]] = []
        batch_started = time.monotonic()

        def flush() -> None:
            nonlocal batch_started
            if not pending:
                return
            try:
                statuses = self.store.insert_many([item[2] for item in pending])
                for (method, properties, _), inserted in zip(pending, statuses):
                    LOGGER.info(
                        "%s event %s",
                        "inserted" if inserted else "duplicate",
                        properties.message_id,
                    )
                    channel.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                LOGGER.exception("Transient consumer batch failure")
                for method, _, _ in pending:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                raise
            finally:
                pending.clear()
                batch_started = time.monotonic()

        for method, properties, body in channel.consume(
            queue=self.settings.queue_name,
            inactivity_timeout=0.5,
            auto_ack=False,
        ):
            if self._stop.is_set():
                break
            if method is None:
                if pending and time.monotonic() - batch_started >= batch_seconds:
                    flush()
                continue
            try:
                event = OrderEvent.model_validate_json(body)
                pending.append((method, properties, event))
            except (ValidationError, ValueError, json.JSONDecodeError) as error:
                record_dead_letter(body, error)
                channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)

            if len(pending) >= batch_size or time.monotonic() - batch_started >= batch_seconds:
                flush()

        if pending and self._connection and self._connection.is_open:
            flush()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = RealtimeSettings.from_env()
    store = RealtimeStore(settings.db_path)
    store.initialize()
    worker = ConsumerWorker(settings, store)

    def stop_worker(*_: object) -> None:
        worker.stop()

    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    worker.run()


if __name__ == "__main__":
    main()

