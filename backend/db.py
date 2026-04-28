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

        # ── Artisans ────────────────────────────────────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artisans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
            """
        )

        # Backward-compatible artisan upgrades
        artisan_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(artisans)").fetchall()
        }
        artisan_new_cols = {
            "bio":          "TEXT",
            "location":     "TEXT",
            "specialty":    "TEXT",
            "years_active": "INTEGER DEFAULT 0",
            "photo_url":    "TEXT",
            "rating":       "REAL DEFAULT 0.0",
            "products_sold":"INTEGER DEFAULT 0",
            "verified":     "INTEGER DEFAULT 0",   # 0 = false, 1 = true
        }
        for col, col_type in artisan_new_cols.items():
            if col not in artisan_cols:
                conn.execute(
                    f"ALTER TABLE artisans ADD COLUMN {col} {col_type}"
                )

        # ── Customers ───────────────────────────────────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                email TEXT,
                password_hash TEXT NOT NULL
            )
            """
        )
        # Backward-compat: add email column if missing
        cust_cols = {row["name"] for row in conn.execute("PRAGMA table_info(customers)").fetchall()}
        if "email" not in cust_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN email TEXT")


        # ── Products ────────────────────────────────────────────────────────
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

        # Backward-compatible product upgrades
        prod_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(products)").fetchall()
        }
        prod_new_cols = {
            "image_url":   "TEXT",
            "image_url_2": "TEXT",
            "image_url_3": "TEXT",
            "image_url_4": "TEXT",
            "materials":   "TEXT",
            "dimensions":  "TEXT",
            "stock":       "INTEGER DEFAULT 0",
            "weight":      "TEXT",
            "care_notes":  "TEXT",
            "tags":        "TEXT",   # comma-separated
            "sync_status": "TEXT DEFAULT 'PENDING'",
            "last_updated": "TEXT",
        }
        for col, col_type in prod_new_cols.items():
            if col not in prod_cols:
                conn.execute(
                    f"ALTER TABLE products ADD COLUMN {col} {col_type}"
                )

        # ── Orders ──────────────────────────────────────────────────────────
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
        if "address" not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN address TEXT")
        if "sync_status" not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN sync_status TEXT DEFAULT 'PENDING'")
        if "last_updated" not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN last_updated TEXT")
        if "dynamo_id" not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN dynamo_id TEXT")

        # ── Shipping ─────────────────────────────────────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shipping (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      INTEGER NOT NULL,
                customer_id     INTEGER NOT NULL,
                customer_name   TEXT    NOT NULL,
                customer_addr   TEXT    NOT NULL,
                FOREIGN KEY (product_id)  REFERENCES products(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
            """
        )

        conn.commit()
    finally:
        if conn is not None:
            conn.close()
