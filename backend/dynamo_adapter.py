"""
dynamo_adapter.py — ArtBridge Data Layer Abstraction
=====================================================

This module provides a unified interface for all database reads.
It routes calls to either SQLite (development/build) or AWS DynamoDB
(production), controlled by the USE_DYNAMO environment variable.

Usage
-----
    USE_DYNAMO=false  →  SQLite via db.py  (default, current)
    USE_DYNAMO=true   →  AWS DynamoDB via boto3

When switching to DynamoDB:
    1. Set USE_DYNAMO=true in your environment / .env file
    2. Fill in TABLE_PRODUCTS, TABLE_ARTISANS, TABLE_ORDERS constants below
    3. Set AWS credentials:
           AWS_ACCESS_KEY_ID=<your_key>
           AWS_SECRET_ACCESS_KEY=<your_secret>
           AWS_DEFAULT_REGION=<e.g. ap-south-1>
    4. Run the data migration script (to be created separately)

DynamoDB Table Design (to create when ready)
--------------------------------------------
    artbridge_products
        PK: id (String)
        Attributes: name, price, description, category, artisan_id,
                    image_url, materials, dimensions, stock, weight,
                    care_notes, tags

    artbridge_artisans
        PK: id (String)
        Attributes: name, bio, location, specialty, years_active,
                    photo_url, rating, products_sold, verified

    artbridge_orders
        PK: id (String)
        Attributes: product_id, artisan_id, buyer, status, tracking,
                    payment_status
"""

import os
import sqlite3
from typing import Optional

# ── Configuration ────────────────────────────────────────────────────────────

USE_DYNAMO: bool = os.environ.get("USE_DYNAMO", "false").lower() == "true"

# DynamoDB table names — fill in when tables are created
TABLE_PRODUCTS = os.environ.get("DYNAMO_TABLE_PRODUCTS", "ArtBridgeProducts")
TABLE_ARTISANS = os.environ.get("DYNAMO_TABLE_ARTISANS", "artbridge_artisans")
TABLE_ORDERS   = os.environ.get("DYNAMO_TABLE_ORDERS",   "ArtBridgeOrders")
TABLE_USERS    = os.environ.get("DYNAMO_TABLE_USERS",    "ArtBridgeUsers")


# ── DynamoDB Client (lazily initialised when USE_DYNAMO=true) ───────────────

_dynamo_resource = None

def _get_dynamo():
    """Return a boto3 DynamoDB resource, initialising once."""
    global _dynamo_resource
    if _dynamo_resource is None:
        try:
            import boto3  # noqa: F401  (only needed in prod)
            _dynamo_resource = boto3.resource(
                "dynamodb",
                region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            )
        except ImportError:
            raise RuntimeError(
                "boto3 is not installed. Run: pip install boto3"
            )
    return _dynamo_resource


# ── Helpers ──────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convert an sqlite3.Row to a plain dict."""
    return dict(row)


# ============================================================
#  PUBLIC API — same signatures regardless of backend
# ============================================================


def get_products() -> list[dict]:
    """Return all products."""
    if USE_DYNAMO:
        return _dynamo_get_products()
    return _sqlite_get_products()


def get_products_by_category(category: str) -> list[dict]:
    """Return products matching a category string (LIKE search)."""
    if USE_DYNAMO:
        return _dynamo_get_products_by_category(category)
    return _sqlite_get_products_by_category(category)


def get_product_with_artisan(product_id: int) -> Optional[dict]:
    """
    Return a single product dict that includes an 'artisan' sub-dict.
    Returns None if the product does not exist.
    """
    if USE_DYNAMO:
        return _dynamo_get_product_with_artisan(product_id)
    return _sqlite_get_product_with_artisan(product_id)


def get_artisan(artisan_id: int) -> Optional[dict]:
    """Return a single artisan dict, or None."""
    if USE_DYNAMO:
        return _dynamo_get_artisan(artisan_id)
    return _sqlite_get_artisan(artisan_id)


# ============================================================
#  SQLite BACKEND
# ============================================================

def _sqlite_conn():
    from db import get_connection
    return get_connection()


def _sqlite_get_products() -> list[dict]:
    conn = None
    try:
        conn = _sqlite_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, price, description, category,
                   artisan_id, image_url, image_url_2, image_url_3, image_url_4,
                   materials, dimensions,
                   stock, weight, care_notes, tags
            FROM products
            ORDER BY id DESC
            """
        )
        return [_row_to_dict(r) for r in cur.fetchall()]
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()


def _sqlite_get_products_by_category(category: str) -> list[dict]:
    conn = None
    try:
        conn = _sqlite_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, price, description, category,
                   artisan_id, image_url, image_url_2, image_url_3, image_url_4,
                   materials, dimensions,
                   stock, weight, care_notes, tags
            FROM products
            WHERE category LIKE ?
            ORDER BY id DESC
            """,
            (f"%{category}%",),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()


def _sqlite_get_product_with_artisan(product_id: int) -> Optional[dict]:
    conn = None
    try:
        conn = _sqlite_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, price, description, category,
                   artisan_id, image_url, image_url_2, image_url_3, image_url_4,
                   materials, dimensions,
                   stock, weight, care_notes, tags
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        product = _row_to_dict(row)

        # Attach artisan if available
        artisan_id = product.get("artisan_id")
        if artisan_id:
            cur.execute(
                """
                SELECT id, name, bio, location, specialty,
                       years_active, photo_url, rating,
                       products_sold, verified
                FROM artisans
                WHERE id = ?
                """,
                (artisan_id,),
            )
            artisan_row = cur.fetchone()
            product["artisan"] = _row_to_dict(artisan_row) if artisan_row else None
        else:
            product["artisan"] = None

        return product
    except sqlite3.Error:
        return None
    finally:
        if conn:
            conn.close()


def _sqlite_get_artisan(artisan_id: int) -> Optional[dict]:
    conn = None
    try:
        conn = _sqlite_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, bio, location, specialty,
                   years_active, photo_url, rating,
                   products_sold, verified
            FROM artisans
            WHERE id = ?
            """,
            (artisan_id,),
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None
    except sqlite3.Error:
        return None
    finally:
        if conn:
            conn.close()


# ============================================================
#  DynamoDB BACKEND  (stub — fill in when tables are ready)
# ============================================================

def _dynamo_get_products() -> list[dict]:
    """
    TODO: Implement when DynamoDB table 'artbridge_products' is ready.

    Example implementation:
        db = _get_dynamo()
        table = db.Table(TABLE_PRODUCTS)
        response = table.scan()
        return response.get("Items", [])
    """
    raise NotImplementedError(
        "DynamoDB backend not yet implemented. "
        "Set USE_DYNAMO=false to use SQLite."
    )


def _dynamo_get_products_by_category(category: str) -> list[dict]:
    """
    TODO: Implement when DynamoDB table is ready.

    Example (using FilterExpression):
        from boto3.dynamodb.conditions import Attr
        db = _get_dynamo()
        table = db.Table(TABLE_PRODUCTS)
        response = table.scan(
            FilterExpression=Attr("category").contains(category)
        )
        return response.get("Items", [])
    """
    raise NotImplementedError("DynamoDB backend not yet implemented.")


def _dynamo_get_product_with_artisan(product_id: int) -> Optional[dict]:
    """
    TODO: Implement when DynamoDB tables are ready.

    Example:
        db = _get_dynamo()
        prod_table = db.Table(TABLE_PRODUCTS)
        product = prod_table.get_item(Key={"id": str(product_id)}).get("Item")
        if not product:
            return None
        artisan_id = product.get("artisan_id")
        if artisan_id:
            artisan_table = db.Table(TABLE_ARTISANS)
            artisan = artisan_table.get_item(
                Key={"id": str(artisan_id)}
            ).get("Item")
            product["artisan"] = artisan
        return product
    """
    raise NotImplementedError("DynamoDB backend not yet implemented.")


def _dynamo_get_artisan(artisan_id: int) -> Optional[dict]:
    """
    TODO: Implement when DynamoDB artisans table is ready.

    Example:
        db = _get_dynamo()
        table = db.Table(TABLE_ARTISANS)
        return table.get_item(Key={"id": str(artisan_id)}).get("Item")
    """
    raise NotImplementedError("DynamoDB backend not yet implemented.")
