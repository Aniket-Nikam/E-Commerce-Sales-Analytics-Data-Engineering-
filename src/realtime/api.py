from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, status
from pika.exceptions import AMQPError

from .consumer import ConsumerWorker
from .messaging import publish_order
from .models import OrderEvent
from .settings import RealtimeSettings
from .store import RealtimeStore

LOGGER = logging.getLogger("realtime-api")
settings = RealtimeSettings.from_env()
store = RealtimeStore(settings.db_path)
consumer: ConsumerWorker | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global consumer
    store.initialize()
    if settings.embed_consumer:
        consumer = ConsumerWorker(settings, store)
        consumer.start()
    yield
    if consumer:
        consumer.stop()


app = FastAPI(
    title="E-Commerce Real-Time Order API",
    version="1.0.0",
    description="Validates order events, publishes them to RabbitMQ, and exposes live DuckDB metrics.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "queue": settings.queue_name,
        "consumer_mode": "embedded" if settings.embed_consumer else "external",
    }


@app.post("/orders", status_code=status.HTTP_202_ACCEPTED)
def create_order(event: OrderEvent) -> dict:
    try:
        publish_order(event, settings)
    except AMQPError as error:
        LOGGER.exception("RabbitMQ publish failed")
        raise HTTPException(status_code=503, detail="Event broker unavailable") from error
    return {
        "status": "accepted",
        "event_id": str(event.event_id),
        "queue": settings.queue_name,
    }


@app.get("/metrics")
def metrics() -> dict:
    return store.metrics()


@app.get("/orders/recent")
def recent_orders(limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    return store.recent(limit)

