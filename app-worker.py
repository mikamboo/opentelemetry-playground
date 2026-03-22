import json
import logging
import os
from time import sleep

import redis
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind, StatusCode
from pythonjsonlogger.json import JsonFormatter

import db

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

tracer = trace.get_tracer(__name__)

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379)

db.init_db()


def process_transfer(job, parent_context=None):
    with tracer.start_as_current_span(
        "process_transfer", context=parent_context, kind=SpanKind.CONSUMER
    ) as span:
        tx_id = job["tx_id"]
        from_id = job["from_account"]
        to_id = job["to_account"]
        amount = job["amount"]
        span.set_attributes(
            {"tx.id": tx_id, "tx.from": from_id, "tx.to": to_id, "tx.amount": amount}
        )

        with db.get_connection() as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id = ?", (from_id,)
            ).fetchone()["balance"]

            if balance < amount:
                conn.execute(
                    "UPDATE transactions SET status = 'failed' WHERE id = ?", (tx_id,)
                )
                span.set_status(StatusCode.ERROR, "Insufficient funds")
                logger.warning(
                    "Transfer failed",
                    extra={"tx_id": tx_id, "reason": "insufficient_funds"},
                )
                return

            conn.execute(
                "UPDATE accounts SET balance = balance - ? WHERE id = ?",
                (amount, from_id),
            )
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE id = ?",
                (amount, to_id),
            )
            conn.execute(
                "UPDATE transactions SET status = 'completed' WHERE id = ?", (tx_id,)
            )

        logger.info(
            "Transfer completed",
            extra={"tx_id": tx_id, "from": from_id, "to": to_id, "amount": amount},
        )


logger.info("Transfer worker started")
while True:
    raw = r.rpop("transfers")
    if raw:
        try:
            job = json.loads(raw)
            job_context = extract(job.get("otel_context", {}))
            with tracer.start_as_current_span(
                "redis.rpop transfers", context=job_context, kind=SpanKind.CONSUMER
            ) as dequeue_span:
                dequeue_span.set_attributes(
                    {
                        "messaging.system": "redis",
                        "messaging.operation": "receive",
                        "messaging.destination.name": "transfers",
                        "tx.id": job.get("tx_id"),
                    }
                )
                process_transfer(
                    job,
                    parent_context=trace.set_span_in_context(dequeue_span, job_context),
                )
        except Exception as e:
            logger.error("Transfer processing error", extra={"error": str(e)})
    sleep(4)  # Simulate processing time
