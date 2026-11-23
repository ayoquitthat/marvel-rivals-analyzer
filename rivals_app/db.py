"""Database connection and setup.

The only configuration is the path to the SQLite file. By default it is
marvel_rivals.db next to main.py; set the MR_DB_PATH environment variable
to use a different file. SQLite needs no server, user name or password.
"""
import os
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_DIR / "schema.sql"
DATA_FILE = PROJECT_DIR / "insert_data.sql"
DB_PATH = Path(os.environ.get("MR_DB_PATH", PROJECT_DIR / "marvel_rivals.db"))


def connect(path=DB_PATH):
    """Open a connection with foreign keys on and rows readable by column name."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # SQLite leaves foreign-key enforcement off unless it is enabled on
    # every new connection, so this must run before any other statement.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def is_initialized(conn):
    """True if the project tables exist in the connected database."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'match_participant'"
    ).fetchone()
    return row[0] == 1


def build_database(conn):
    """(Re)create every table, index and view, then load the sample data.

    Runs the same schema.sql and insert_data.sql files submitted with the
    backend, so the application and the SQL scripts always match.
    """
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.executescript(DATA_FILE.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")
