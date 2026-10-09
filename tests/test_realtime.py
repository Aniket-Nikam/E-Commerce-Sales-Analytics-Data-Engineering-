from decimal import Decimal
import pytest
from pydantic import ValidationError

from src.realtime.consumer import process_message
from src.realtime.messaging import publish_order
from src.realtime.models import OrderEvent
from src.realtime.settings import RealtimeSettings
from src.realtime.store import RealtimeStore


def valid_event() -> OrderEvent:
    return OrderEvent(
        order_id="LIVE-TEST-001",
        customer_id="C000001",
        product_id="P001",
        category="Electronics",
        quantity=2,
        unit_price=Decimal("125.50"),
        discount_pct=Decimal("0.10"),
        region="West",
        sales_channel="Web",
    )


def test_realtime_store_is_idempotent(tmp_path):
    store = RealtimeStore(tmp_path / "realtime.duckdb")
    store.initialize()
    event = valid_event()

    assert process_message(event.model_dump_json().encode(), store) == "inserted"
    assert process_message(event.model_dump_json().encode(), store) == "duplicate"

    metrics = store.metrics()
    assert metrics["total_events"] == 1
    assert metrics["live_customers"] == 1
    assert metrics["live_revenue"] == pytest.approx(225.90)
    assert store.recent(10)[0]["order_id"] == "LIVE-TEST-001"


def test_realtime_payload_validation_rejects_invalid_quantity():
    with pytest.raises(ValidationError):
        OrderEvent(
            order_id="LIVE-TEST-002",
            customer_id="C000002",
            product_id="P002",
            category="Books",
            quantity=0,
            unit_price=Decimal("25.00"),
            region="North",
            sales_channel="Mobile App",
        )


def test_publisher_declares_durable_queue_and_persistent_message(tmp_path, monkeypatch):
    recorded: dict = {}

    class FakeChannel:
        def queue_declare(self, **kwargs):
            recorded["queue"] = kwargs

        def confirm_delivery(self):
            recorded["confirm_delivery"] = True

        def basic_publish(self, **kwargs):
            recorded["publish"] = kwargs
            return True

    class FakeConnection:
        def __init__(self, parameters):
            recorded["parameters"] = parameters

        def channel(self):
            return FakeChannel()

        def close(self):
            recorded["closed"] = True

    monkeypatch.setattr("src.realtime.messaging.pika.BlockingConnection", FakeConnection)
    settings = RealtimeSettings(
        rabbitmq_url="amqp://guest:guest@localhost:5672/%2F",
        queue_name="test.order.events",
        db_path=tmp_path / "realtime.duckdb",
        embed_consumer=False,
    )

    event = valid_event()
    publish_order(event, settings)

    assert recorded["queue"] == {"queue": "test.order.events", "durable": True}
    assert recorded["publish"]["routing_key"] == "test.order.events"
    assert recorded["publish"]["properties"].delivery_mode == 2
    assert recorded["confirm_delivery"] is True
    assert recorded["closed"] is True
