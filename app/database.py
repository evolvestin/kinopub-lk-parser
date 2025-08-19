import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from config import DB_PATH, CODE_LIFETIME_MINUTES


@contextmanager
def db_connection():
    """Context manager for SQLite connection."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        yield conn
    except sqlite3.Error as e:
        logging.error("Database connection error: %s", e)
        raise
    finally:
        if conn:
            conn.close()


def init_db():
    """Initializes the database and creates the 'codes' table if it doesn't exist."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    telegram_message_id INTEGER NOT NULL,
                    received_at TEXT NOT NULL -- CHANGED: Storing timestamp as ISO 8601 string
                )
            ''')
            conn.commit()
            logging.info("Database initialized successfully at %s.", DB_PATH)
    except sqlite3.Error as e:
        logging.error("Failed to initialize database: %s", e)
        raise


def add_code(code: str, telegram_message_id: int, received_at: str):
    """Adds a new code to the database."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO codes (code, telegram_message_id, received_at) VALUES (?, ?, ?)",
                (code, telegram_message_id, received_at)
            )
            conn.commit()
            logging.info("Code %s (msg_id: %d) added to the database.", code, telegram_message_id)
    except sqlite3.Error as e:
        logging.error("Failed to add code %s to database: %s", code, e)


def get_expired_codes():
    """Retrieves all codes that have expired based on ISO timestamp."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            expiration_threshold = datetime.now(timezone.utc) - timedelta(minutes=CODE_LIFETIME_MINUTES)
            expiration_threshold_iso = expiration_threshold.isoformat()

            cursor.execute(
                "SELECT id, telegram_message_id FROM codes WHERE received_at < ?",
                (expiration_threshold_iso,)
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error("Failed to retrieve expired codes: %s", e)
        return []


def delete_code(code_id: int):
    """Deletes a code from the database by its ID."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM codes WHERE id = ?", (code_id,))
            conn.commit()
            logging.info("Code with id=%d deleted from the database.", code_id)
    except sqlite3.Error as e:
        logging.error("Failed to delete code with id=%d: %s", code_id, e)
