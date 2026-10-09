from __future__ import annotations

import pika

from .models import OrderEvent
from .settings import RealtimeSettings


def publish_order(event: OrderEvent, settings: RealtimeSettings) -> None:
    parameters = pika.URLParameters(settings.rabbitmq_url)
    parameters.heartbeat = 30
    parameters.blocked_connection_timeout = 30
    connection = pika.BlockingConnection(parameters)
    try:
        channel = connection.channel()
        channel.queue_declare(queue=settings.queue_name, durable=True)
        channel.confirm_delivery()
        confirmed = channel.basic_publish(
            exchange="",
            routing_key=settings.queue_name,
            body=event.model_dump_json().encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=pika.DeliveryMode.Persistent,
                message_id=str(event.event_id),
                timestamp=int(event.event_time.timestamp()),
            ),
            mandatory=True,
        )
        if confirmed is False:
            raise pika.exceptions.NackError("RabbitMQ did not confirm the order event")
    finally:
        connection.close()
