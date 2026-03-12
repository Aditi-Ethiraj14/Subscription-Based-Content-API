import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "subscription_api.db")

# Singleton for :memory: (each new sqlite3.connect(':memory:') is a fresh DB)
_memory_conn = None


def get_db():
    global _memory_conn
    if DB_PATH == ":memory:":
        if _memory_conn is None:
            _memory_conn = _MemoryConn(":memory:")
        return _memory_conn

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class _MemoryConn:
    """Wrapper around a persistent in-memory connection that ignores close()."""
    def __init__(self, path):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")

    def close(self):
        pass  # never close the shared in-memory connection

    def __getattr__(self, name):
        return getattr(self._conn, name)


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE,
            email       TEXT    NOT NULL UNIQUE,
            password_hash TEXT  NOT NULL,
            role        TEXT    NOT NULL DEFAULT 'free'  CHECK(role IN ('free','premium','admin')),
            subscribed_at   TEXT,
            expires_at      TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS content (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            body        TEXT    NOT NULL,
            tier        TEXT    NOT NULL DEFAULT 'free' CHECK(tier IN ('free','premium')),
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS access_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER REFERENCES users(id),
            content_id  INTEGER REFERENCES content(id),
            endpoint    TEXT    NOT NULL,
            method      TEXT    NOT NULL,
            status_code INTEGER NOT NULL,
            ip_address  TEXT,
            user_agent  TEXT,
            accessed_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            amount          REAL    NOT NULL,
            currency        TEXT    NOT NULL DEFAULT 'USD',
            status          TEXT    NOT NULL CHECK(status IN ('pending','success','failed')),
            transaction_ref TEXT    NOT NULL UNIQUE,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)

    # Seed sample content
    cursor.execute("SELECT COUNT(*) FROM content")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO content (title, body, tier) VALUES (?,?,?)",
            [
                ("Welcome Article",        "This is free content available to all users.",      "free"),
                ("Getting Started Guide",  "Another free article to help you get started.",     "free"),
                ("Advanced Techniques",    "This premium article covers advanced techniques.",  "premium"),
                ("Exclusive Report Q1",    "Detailed quarterly report — premium members only.", "premium"),
                ("Deep Dive: Architecture","In-depth architecture guide for subscribers.",      "premium"),
            ]
        )

    conn.commit()
    conn.close()
    print(f"Database initialised at: {DB_PATH}")
