#!/usr/bin/env python3
"""
database.py — SQLite database manager.

products table now has four explicit photo columns:
    photo_path1, photo_path2, photo_path3, photo_path4
All four absolute paths are stored directly — no separate join table needed.
The legacy photo_path column is kept as an alias for photo_path1 for any
code that still reads it.
"""

import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiosk.db")


class DatabaseManager:
    """Thread-safe SQLite wrapper for all kiosk data."""

    def __init__(self, db_path: str = DB_PATH):
        self._path = db_path
        self._create_tables()
        try:
            self._migrate()
        except Exception as e:
            print(f"[DB] ⚠️  Migration skipped (DB busy?): {e}")
        self._seed_demo_data()
        
        # Ensure photo directory exists
        photo_dir = os.path.join(os.path.dirname(self._path), "artbridge_photos")
        if not os.path.exists(photo_dir):
            os.makedirs(photo_dir)
            print(f"[DB] Created photo directory: {photo_dir}")

    # ── Schema ────────────────────────────────────────────────────────────────
    def _create_tables(self):
        # Set WAL mode FIRST in a separate connection
        # (executescript resets connection state, so WAL must be set before it)
        with sqlite3.connect(self._path, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")

        # Now create tables
        with sqlite3.connect(self._path, timeout=30) as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL,
                fingerprint_id INTEGER UNIQUE,
                created_at     TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                description  TEXT,
                price        REAL    NOT NULL DEFAULT 0,
                category     TEXT    DEFAULT 'General',
                photo_path   TEXT,
                photo_path1  TEXT,
                photo_path2  TEXT,
                photo_path3  TEXT,
                photo_path4  TEXT,
                image_url    TEXT,
                image_url_2  TEXT,
                image_url_3  TEXT,
                image_url_4  TEXT,
                synced       INTEGER DEFAULT 0,
                sync_status  TEXT    DEFAULT 'PENDING',
                last_updated TEXT,
                created_at   TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id   INTEGER REFERENCES products(id),
                product_name TEXT,
                customer     TEXT,
                amount       REAL,
                status       TEXT    DEFAULT 'Pending',
                dynamo_id    TEXT    UNIQUE,
                created_at   TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS shipping_details (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id         INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id       INTEGER REFERENCES products(id),
                customer_name    TEXT    NOT NULL,
                customer_address TEXT    NOT NULL,
                created_at       TEXT    DEFAULT (datetime('now'))
            );
            """)

    def _migrate(self):
        """
        Add photo_path1-4 columns to existing databases that were created
        before this schema change.  Safe to run on a fresh DB too.
        """
        with sqlite3.connect(self._path, timeout=20) as conn:
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(products)").fetchall()
            }
            for col in ("photo_path1", "photo_path2", "photo_path3", "photo_path4"):
                if col not in existing:
                    conn.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT")
            # Back-fill photo_path1 from old photo_path column where missing
            if "photo_path" in existing:
                conn.execute("""
                    UPDATE products
                    SET    photo_path1 = photo_path
                    WHERE  photo_path IS NOT NULL
                    AND    photo_path1 IS NULL
                """)
            
            # Add new columns requested
            for col, col_def in [
                ("sync_status", "TEXT DEFAULT 'PENDING'"),
                ("last_updated", "TEXT"),
                ("synced", "INTEGER DEFAULT 0"),
                ("created_at", "TEXT"),
                ("image_url", "TEXT"),
                ("image_url_2", "TEXT"),
                ("image_url_3", "TEXT"),
                ("image_url_4", "TEXT"),
            ]:
                if col not in existing:
                    conn.execute(f"ALTER TABLE products ADD COLUMN {col} {col_def}")
        # Add new columns to orders
        with sqlite3.connect(self._path, timeout=20) as conn:
            existing_orders = {
                row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()
            }
            if "dynamo_id" not in existing_orders:
                conn.execute("ALTER TABLE orders ADD COLUMN dynamo_id TEXT")
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_dynamo_id ON orders(dynamo_id)")

    def _seed_demo_data(self):
        """Insert demo products/orders only if the tables are empty."""
        with sqlite3.connect(self._path, timeout=20) as conn:
            if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
                demo_products = [
                    ("Handmade Pot",  "Traditional clay pot",   350.0, "Pottery",  None, None, None, None),
                    ("Silk Saree",    "Pure silk weave",        2800.0, "Textile",  None, None, None, None),
                    ("Bamboo Basket", "Eco-friendly basket",     180.0, "Bamboo",   None, None, None, None),
                    ("Wooden Toy",    "Hand-carved toy",         250.0, "Woodwork", None, None, None, None),
                    ("Bronze Idol",   "Traditional brass idol", 1500.0, "Metal",    None, None, None, None),
                ]
                conn.executemany(
                    "INSERT INTO products (name, description, price, category, image_url, image_url_2, image_url_3, image_url_4) VALUES (?,?,?,?,?,?,?,?)",
                    demo_products,
                )

            if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
                demo_orders = [
                    ("Handmade Pot",  "Ravi Kumar",  350.0,  "Delivered"),
                    ("Silk Saree",    "Meena Devi",  2800.0, "Pending"),
                    ("Bamboo Basket", "Suresh Babu",  180.0, "Shipped"),
                ]
                conn.executemany(
                    "INSERT INTO orders (product_name,customer,amount,status) VALUES (?,?,?,?)",
                    demo_orders,
                )

    # ── Users ─────────────────────────────────────────────────────────────────
    def add_user(self, name: str, fingerprint_id: int) -> int:
        with sqlite3.connect(self._path, timeout=20) as conn:
            cur = conn.execute(
                "INSERT INTO users (name, fingerprint_id) VALUES (?, ?)",
                (name, fingerprint_id),
            )
            return cur.lastrowid

    def get_user_by_fingerprint(self, fingerprint_id: int):
        with sqlite3.connect(self._path, timeout=20) as conn:
            row = conn.execute(
                "SELECT id, name FROM users WHERE fingerprint_id = ?",
                (fingerprint_id,),
            ).fetchone()
        return row  # (id, name) | None

    # ── Products ──────────────────────────────────────────────────────────────
    def get_products(self):
        with sqlite3.connect(self._path, timeout=20) as conn:
            return conn.execute(
                "SELECT id, name, price, category, synced, created_at "
                "FROM products ORDER BY id DESC"
            ).fetchall()

    def add_product(self, name: str, description: str, price: float,
                    category: str = "General",
                    photo_path: str = None,
                    photo_paths: list = None,
                    image_urls: list = None) -> int:
        """
        Save a product with up to 4 photos and optional S3 image URLs.

        photo_paths — list of up to 4 absolute file paths (from camera slots).
                      None / "placeholder" entries are stored as NULL.
        photo_path  — legacy single-path arg; used as photo_path1 if
                      photo_paths is not supplied.
        image_urls  — list of up to 4 S3 public URLs (from s3_uploader).
                      None entries are stored as NULL.

        Columns written:
            photo_path   = slot-1 path  (backward-compat alias)
            photo_path1  = slot 1 absolute path (or NULL)
            photo_path2  = slot 2 absolute path (or NULL)
            photo_path3  = slot 3 absolute path (or NULL)
            photo_path4  = slot 4 absolute path (or NULL)
            image_url    = S3 URL for slot 1 (or NULL)
            image_url_2  = S3 URL for slot 2 (or NULL)
            image_url_3  = S3 URL for slot 3 (or NULL)
            image_url_4  = S3 URL for slot 4 (or NULL)
            sync_status  = 'PENDING'
        """
        def _clean(p):
            """Return path if it is a real non-placeholder string, else None."""
            return p if (p and p != "placeholder") else None

        if photo_paths:
            # Pad / trim to exactly 4 slots
            slots = (list(photo_paths) + [None, None, None, None])[:4]
            p1, p2, p3, p4 = [_clean(s) for s in slots]
        else:
            p1 = _clean(photo_path)
            p2 = p3 = p4 = None

        primary = p1  # backward-compat column = slot 1

        # S3 image URLs (may be None if upload was skipped)
        urls = (list(image_urls or []) + [None, None, None, None])[:4]
        u1, u2, u3, u4 = urls

        try:
            with sqlite3.connect(self._path, timeout=20) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO products
                        (name, description, price, category,
                         photo_path, photo_path1, photo_path2, photo_path3, photo_path4,
                         image_url, image_url_2, image_url_3, image_url_4,
                         sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                    """,
                    (name, description, price, category,
                     primary, p1, p2, p3, p4,
                     u1, u2, u3, u4),
                )
                pid = cur.lastrowid
                print(f"[DB] ✅ Product stored successfully: ID {pid} ({name})")
                return pid
        except Exception as e:
            print(f"[DB] ❌ FAILED TO STORE PRODUCT: {e}")
            return -1

    def get_product_photo(self, product_id: int) -> str:
        """Return the primary (slot 1) photo path, or None."""
        with sqlite3.connect(self._path, timeout=20) as conn:
            row = conn.execute(
                "SELECT photo_path1, photo_path FROM products WHERE id=?",
                (product_id,),
            ).fetchone()
        if not row:
            return None
        return row[0] or row[1]   # prefer photo_path1, fall back to legacy

    def _get_local_photos(self, product_id: int) -> list:
        """Return list of non-null local photo paths (slots 1-4) for a product."""
        with sqlite3.connect(self._path, timeout=20) as conn:
            row = conn.execute(
                "SELECT photo_path1, photo_path2, photo_path3, photo_path4 FROM products WHERE id=?",
                (product_id,)
            ).fetchone()
        if not row:
            return []
        return [p for p in row if p]

    def get_product_photos(self, product_id: int) -> list:
        """Alias for _get_local_photos required by screens_main.py."""
        return self._get_local_photos(product_id)

    def get_product_image_urls(self, product_id: int) -> list:
        """
        Return a list of all non-null S3 image URLs for the product,
        ordered slot 1 → 4.
        """
        with sqlite3.connect(self._path, timeout=20) as conn:
            row = conn.execute(
                "SELECT image_url, image_url_2, image_url_3, image_url_4 FROM products WHERE id=?",
                (product_id,)
            ).fetchone()
        if not row:
            return []
        urls = [url for url in row if url]
        return urls

    def update_product_image_urls(self, product_id: int, urls: list):
        """
        Write S3 image URLs (list of up to 4) back to the product row
        and mark it as PENDING so the sync process picks it up.
        """
        padded = (list(urls) + [None, None, None, None])[:4]
        with sqlite3.connect(self._path, timeout=20) as conn:
            conn.execute(
                """UPDATE products
                   SET image_url=?, image_url_2=?, image_url_3=?, image_url_4=?,
                       sync_status='PENDING'
                   WHERE id=?""",
                (*padded, product_id),
            )
        print(f"[DB] Updated S3 URLs for product {product_id}: {padded}")

    def get_product_description(self, product_id: int):
        try:
            with sqlite3.connect(self._path, timeout=20) as conn:
                row = conn.execute(
                    "SELECT description FROM products WHERE id=?", (product_id,)
                ).fetchone()
            return row[0] if row else None
        except Exception:
            return None

    # ── Orders ────────────────────────────────────────────────────────────────
    def get_orders(self):
        """
        Return orders joined with shipping_details.
        Columns: id, product_name, customer, amount, status,
                 created_at, customer_name, customer_address
        """
        with sqlite3.connect(self._path, timeout=20) as conn:
            return conn.execute("""
                SELECT
                    o.id,
                    o.product_name,
                    o.customer,
                    o.amount,
                    o.status,
                    o.created_at,
                    s.customer_name,
                    s.customer_address
                FROM orders o
                LEFT JOIN shipping_details s ON s.order_id = o.id
                ORDER BY o.id DESC
            """).fetchall()

    def add_shipping_detail(self, order_id: int, product_id: int,
                            customer_name: str, customer_address: str):
        with sqlite3.connect(self._path, timeout=20) as conn:
            conn.execute(
                "INSERT INTO shipping_details "
                "(order_id, product_id, customer_name, customer_address) "
                "VALUES (?,?,?,?)",
                (order_id, product_id, customer_name, customer_address),
            )

    # ── Earnings ──────────────────────────────────────────────────────────────
    def get_earnings(self):
        """Return (total_revenue, total_orders, pending_orders, synced_products)."""
        with sqlite3.connect(self._path, timeout=20) as conn:
            total_rev = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='Delivered'"
            ).fetchone()[0]
            total_ord = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            pending   = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE status='Pending'"
            ).fetchone()[0]
            synced    = conn.execute(
                "SELECT COUNT(*) FROM products WHERE synced=1"
            ).fetchone()[0]
        return total_rev, total_ord, pending, synced

    def mark_all_synced(self):
        with sqlite3.connect(self._path, timeout=20) as conn:
            conn.execute("UPDATE products SET synced=1 WHERE synced=0")
