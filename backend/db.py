import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/config/tracker.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                search_query TEXT NOT NULL,
                target_price REAL NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                retailer TEXT NOT NULL,
                price REAL NOT NULL,
                url TEXT,
                checked_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (part_id) REFERENCES parts(id)
            );

            CREATE TABLE IF NOT EXISTS alert_state (
                part_id INTEGER NOT NULL,
                retailer TEXT NOT NULL,
                last_alerted_price REAL,
                PRIMARY KEY (part_id, retailer),
                FOREIGN KEY (part_id) REFERENCES parts(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                discord_webhook TEXT DEFAULT '',
                email_from TEXT DEFAULT '',
                email_to TEXT DEFAULT '',
                email_password TEXT DEFAULT '',
                email_smtp_host TEXT DEFAULT 'smtp.gmail.com',
                email_smtp_port INTEGER DEFAULT 587,
                check_interval_minutes INTEGER DEFAULT 60,
                total_budget REAL DEFAULT 0,
                pricesapi_key TEXT DEFAULT ''
            );
        """)
        # Migrate existing DBs that predate pricesapi_key column
        try:
            db.execute("ALTER TABLE settings ADD COLUMN pricesapi_key TEXT DEFAULT ''")
        except Exception:
            pass  # column already exists, that's fine


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
