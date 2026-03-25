import os
import sqlite3
from typing import Optional


def get_db_path() -> str:
    """
    Single, shared DB for the entire project:
    <project_root>/artbridge.db
    """
    here = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(here, ".."))
    return os.path.join(project_root, "artbridge.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = get_connection()

        # Minimal artisan table (for future modules / referential integrity).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artisans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                category TEXT,
                artisan_id INTEGER,
                FOREIGN KEY (artisan_id) REFERENCES artisans(id)
            )
            """
        )

        # Backward-compatible schema upgrade: add image_url if missing.
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(products)").fetchall()
        }
        if "image_url" not in cols:
            conn.execute("ALTER TABLE products ADD COLUMN image_url TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                artisan_id INTEGER,
                buyer TEXT NOT NULL,
                status TEXT NOT NULL,
                tracking TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (artisan_id) REFERENCES artisans(id)
            )
            """
        )

        order_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(orders)").fetchall()
        }
        if "payment_status" not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT")

        conn.commit()
    finally:
        if conn is not None:
            conn.close()

