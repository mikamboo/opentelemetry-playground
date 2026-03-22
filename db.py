import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "bank.db")


class _TracedConnection:
    """Routes execute() through cursor() so the OTel sqlite3 instrumentor
    can create spans.  sqlite3.Connection.execute() is a C-level shortcut
    that bypasses the Python cursor() method that the instrumentor patches."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, parameters=()):
        return self._conn.cursor().execute(sql, parameters)

    def executemany(self, sql, seq_of_parameters):
        return self._conn.cursor().executemany(sql, seq_of_parameters)

    def executescript(self, sql_script):
        # executescript is not traced by the instrumentor but keep it working
        return self._conn.executescript(sql_script)

    def cursor(self):
        return self._conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
        return False


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return _TracedConnection(conn)


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
