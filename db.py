import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "bank.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id      TEXT PRIMARY KEY,
                name    TEXT NOT NULL,
                balance REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                from_account TEXT NOT NULL,
                to_account   TEXT NOT NULL,
                amount       REAL NOT NULL,
                status       TEXT NOT NULL,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO accounts (id, name, balance) VALUES (?, ?, ?)",
                [
                    ("ACC001", "Alice", 1000.00),
                    ("ACC002", "Bob", 500.00),
                    ("ACC003", "Charlie", 2500.00),
                    ("ACC004", "Diana", 750.00),
                ],
            )
