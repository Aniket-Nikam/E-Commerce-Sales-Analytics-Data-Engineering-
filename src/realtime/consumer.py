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
        channel.basic_qos(prefetch_count=25)

        def callback(ch, method, properties, body: bytes) -> None:
            try:
                status = process_message(body, self.store)
                LOGGER.info("%s event %s", status, properties.message_id)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except (ValidationError, ValueError, json.JSONDecodeError) as error:
                record_dead_letter(body, error)
                ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            except Exception:
                LOGGER.exception("Transient consumer failure")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        channel.basic_consume(queue=self.settings.queue_name, on_message_callback=callback)
        channel.start_consuming()


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

