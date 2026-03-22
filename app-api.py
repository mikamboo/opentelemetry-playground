import json
import logging
import os

import redis
from flask import Flask, jsonify, request
from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind, StatusCode
from pythonjsonlogger.json import JsonFormatter

import db

# from opentelemetry.instrumentation.flask import FlaskInstrumentor

app = Flask(__name__)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379)

db.init_db()

# FlaskInstrumentor().instrument_app(app)


@app.route("/api/accounts")
def get_accounts():
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/transfer", methods=["POST"])
def transfer():
    data = request.get_json()
    from_id = data.get("from_account")
    to_id = data.get("to_account")
    amount = float(data.get("amount", 0))

    if not from_id or not to_id or from_id == to_id:
        return jsonify({"error": "Invalid accounts"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    with tracer.start_as_current_span("transfer.create") as create_span:
        create_span.set_attributes(
            {"tx.from": from_id, "tx.to": to_id, "tx.amount": amount}
        )
        with db.get_connection() as conn:
            from_acc = conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (from_id,)
            ).fetchone()
            to_acc = conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (to_id,)
            ).fetchone()

            if not from_acc or not to_acc:
                create_span.set_status(StatusCode.ERROR, "Account not found")
                return jsonify({"error": "Account not found"}), 404
            if from_acc["balance"] < amount:
                create_span.set_status(StatusCode.ERROR, "Insufficient funds")
                return jsonify({"error": "Insufficient funds"}), 400

            cursor = conn.execute(
                "INSERT INTO transactions (from_account, to_account, amount, status) VALUES (?, ?, ?, 'pending')",
                (from_id, to_id, amount),
            )
            tx_id = cursor.lastrowid
            create_span.set_attribute("tx.id", tx_id)

    with tracer.start_as_current_span(
        "redis.rpush transfers", kind=SpanKind.PRODUCER
    ) as queue_span:
        queue_span.set_attributes(
            {
                "messaging.system": "redis",
                "messaging.operation": "publish",
                "messaging.destination.name": "transfers",
                "tx.id": tx_id,
            }
        )

        # Inject this producer span context so dequeue stays on the same trace.
        otel_context = {}
        inject(otel_context)
        job = {
            "tx_id": tx_id,
            "from_account": from_id,
            "to_account": to_id,
            "amount": amount,
            "otel_context": otel_context,
        }

        try:
            r.rpush("transfers", json.dumps(job))
        except Exception as e:
            queue_span.record_exception(e)
            queue_span.set_status(StatusCode.ERROR, "Queue publish failed")
            raise

    logger.info(
        "Transfer queued",
        extra={"tx_id": tx_id, "from": from_id, "to": to_id, "amount": amount},
    )
    return jsonify({"status": "queued", "tx_id": tx_id})


@app.route("/api/transactions")
def get_transactions():
    with tracer.start_as_current_span("db.query transactions") as span:
        with db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT t.*, a1.name AS from_name, a2.name AS to_name
                FROM transactions t
                JOIN accounts a1 ON t.from_account = a1.id
                JOIN accounts a2 ON t.to_account = a2.id
                ORDER BY t.created_at DESC
                LIMIT 20
            """
            ).fetchall()
        span.set_attribute("transactions.count", len(rows))
        if rows:
            span.set_attribute("transactions.latest_id", rows[0]["id"])
            statuses = list({row["status"] for row in rows})
            span.set_attribute("transactions.statuses", ",".join(statuses))
    return jsonify([dict(row) for row in rows])
