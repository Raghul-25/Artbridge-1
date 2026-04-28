import sqlite3
import os
import time
import logging
from datetime import datetime
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sync.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiosk.db")
DYNAMO_TABLE = "ArtBridgeProducts"
DYNAMO_TABLE_ORDERS = os.environ.get("DYNAMO_TABLE_ORDERS", "ArtBridgeOrders")
REGION       = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
MAX_RETRIES  = 3
RETRY_DELAY  = 2  # seconds

# Fields that must NEVER be pushed to DynamoDB (local-only paths, legacy columns)
_LOCAL_ONLY_FIELDS = {
    "photo_path", "photo_path1", "photo_path2", "photo_path3", "photo_path4",
    "synced",       # internal boolean, not useful for frontend
    "sync_status", # exclude local sync status from DynamoDB
}

def _get_dynamo_table():
    try:
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        # Force a connectivity check
        table = dynamodb.Table(DYNAMO_TABLE)
        table.table_status
        return table
    except Exception as e:
        logger.error(f"AWS/DynamoDB Error: {e}")
        logger.error("TIP: Ensure your Pi has AWS credentials configured in ~/.aws/credentials")
        raise

def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def _is_s3_url(value: str) -> bool:
    """Return True only if the value looks like a valid S3 HTTPS URL."""
    return isinstance(value, str) and value.startswith("https://")

def _is_local_path(value: str) -> bool:
    """Detect Windows/Unix local file paths."""
    if not isinstance(value, str):
        return False
    return value.startswith("C:\\") or value.startswith("/") or value.startswith("C:/")

def _build_dynamo_item(product: dict) -> dict:
    """
    Convert a SQLite product row into a clean DynamoDB item.

    Rules:
    - Strip all local-only fields (_LOCAL_ONLY_FIELDS)
    - Strip any field whose value is a local file path
    - Only include image_url fields if they are valid S3 URLs
    - Convert floats → Decimal, ints → str for id
    - Always set last_updated timestamp
    """
    item = {}

    for k, v in product.items():
        # Skip local-only structural fields
        if k in _LOCAL_ONLY_FIELDS:
            continue

        # Skip null / empty values
        if v is None or v == "":
            continue

        # Skip any field that contains a local file path
        if _is_local_path(str(v)):
            logger.debug(f"  Skipping field '{k}' — local path: {v}")
            continue

        # Convert floats to Decimal (DynamoDB requirement)
        if isinstance(v, float):
            v = Decimal(str(v))

        item[k] = v

    # ── Enforce required fields ──────────────────────────────────────────────
    item['id']           = str(item['id'])
    item['sync_status'] = 'SYNCED'

    # ── Validate image fields — keep only real S3 URLs ───────────────────────
    for img_field in ("image_url", "image_url_2", "image_url_3", "image_url_4"):
        val = item.get(img_field)
        if val and not _is_s3_url(str(val)):
            logger.warning(f"  Removing '{img_field}' — not a valid S3 URL: {val}")
            del item[img_field]

    # ── Ensure price is Decimal ───────────────────────────────────────────────
    if 'price' in item and not isinstance(item['price'], Decimal):
        try:
            item['price'] = Decimal(str(item['price']))
        except Exception:
            pass

    return item


def sync_products_to_dynamo():
    logger.info("=" * 60)
    logger.info("Starting sync process...")

    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        return

    try:
        table = _get_dynamo_table()
    except Exception as e:
        logger.error(f"Aborting sync: Cannot connect to AWS DynamoDB: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _dict_factory
    cur = conn.cursor()

    try:
        cur.execute("SELECT * FROM products WHERE sync_status = 'PENDING'")
        pending = cur.fetchall()

        if not pending:
            logger.info("No pending products to sync.")
            return

        logger.info(f"Found {len(pending)} pending products.")
        synced_count = 0
        failed_count = 0

        for product in pending:
            pid  = product['id']
            name = product.get('name', '?')
            logger.info(f"  Processing product ID {pid} — {name}")

            # Build clean DynamoDB item (no local paths)
            try:
                item = _build_dynamo_item(product)
            except Exception as e:
                logger.error(f"  Failed to build item for {pid}: {e}")
                failed_count += 1
                continue

            # Log image fields being pushed
            for f in ("image_url", "image_url_2", "image_url_3", "image_url_4"):
                if f in item:
                    logger.info(f"  {f} = {item[f]}")
                else:
                    logger.debug(f"  {f} = (not set)")

            # Push to DynamoDB with retry
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    table.put_item(Item=item)
                    success = True
                    break
                except ClientError as e:
                    logger.warning(f"  DynamoDB error attempt {attempt}/{MAX_RETRIES}: {e}")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    logger.error(f"  Unexpected error: {e}")
                    break

            # Update SQLite status
            if success:
                try:
                    cur.execute(
                        "UPDATE products SET sync_status = 'SYNCED', last_updated = ? WHERE id = ?",
                        (datetime.utcnow().isoformat() + "Z", pid)
                    )
                    conn.commit()
                    logger.info(f"  [OK] Product {pid} synced successfully.")
                    synced_count += 1
                except sqlite3.Error as db_err:
                    logger.error(f"  Failed to update SQLite for product {pid}: {db_err}")
            else:
                logger.error(f"  [FAIL] Product {pid} failed after {MAX_RETRIES} attempts.")
                failed_count += 1

        logger.info(f"Sync complete — {synced_count} synced, {failed_count} failed.")

    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
    finally:
        conn.close()
        logger.info("Sync process finished.")
        logger.info("=" * 60)


def sync_orders_from_dynamo(db_manager=None):
    """
    Pulls orders from DynamoDB and inserts any new ones into the local SQLite orders table.
    """
    logger.info("Starting order sync from DynamoDB...")
    try:
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table(DYNAMO_TABLE_ORDERS)
        response = table.scan()
        cloud_orders = response.get('Items', [])
    except Exception as e:
        logger.error(f"Failed to fetch orders from DynamoDB: {e}")
        return

    if not cloud_orders:
        logger.info("No orders found in cloud.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        inserted_count = 0
        for d_order in cloud_orders:
            dynamo_id = d_order.get('id')
            if not dynamo_id:
                continue

            # Check if order already exists locally
            cur.execute("SELECT id FROM orders WHERE dynamo_id = ?", (dynamo_id,))
            existing = cur.fetchone()
            if existing:
                # Order exists — back-fill shipping_details if missing
                local_order_id = existing['id']
                cur.execute(
                    "SELECT id FROM shipping_details WHERE order_id = ?",
                    (local_order_id,)
                )
                if not cur.fetchone():
                    customer_name = d_order.get('customer_name', '') or d_order.get('customer', '')
                    address       = d_order.get('address', '') or d_order.get('customer_address', '')
                    product_id    = d_order.get('product_id')
                    if customer_name or address:
                        cur.execute(
                            "INSERT INTO shipping_details "
                            "(order_id, product_id, customer_name, customer_address) "
                            "VALUES (?, ?, ?, ?)",
                            (local_order_id, product_id, customer_name, address)
                        )
                        logger.info(f"  [SHIPPING] Back-filled shipping for order {local_order_id}.")
                continue

            # ── New order — insert into orders ──────────────────────────────
            product_id   = d_order.get('product_id')
            product_name = "Unknown Product"
            amount       = 0.0

            if product_id:
                cur.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
                prod_row = cur.fetchone()
                if prod_row:
                    product_name = prod_row['name']
                    amount       = float(prod_row['price'])

            customer   = d_order.get('customer_name', 'Customer')
            d_status   = d_order.get('status', 'Processing')
            status     = 'Pending' if d_status in ('PLACED', 'Processing') else d_status
            created_at = d_order.get('created_at', datetime.utcnow().isoformat() + "Z")

            cur.execute(
                """
                INSERT INTO orders (product_id, product_name, customer, amount, status, dynamo_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (product_id, product_name, customer, amount, status, dynamo_id, created_at)
            )
            local_order_id = cur.lastrowid

            # ── Also store shipping details ──────────────────────────────────
            ship_name    = d_order.get('customer_name', '') or customer
            ship_address = d_order.get('address', '') or d_order.get('customer_address', 'Address not provided')
            cur.execute(
                "INSERT INTO shipping_details "
                "(order_id, product_id, customer_name, customer_address) "
                "VALUES (?, ?, ?, ?)",
                (local_order_id, product_id, ship_name, ship_address)
            )

            inserted_count += 1
            logger.info(f"  [OK] Pulled order {dynamo_id} — '{ship_name}' @ '{ship_address}'")

        conn.commit()
        logger.info(f"Order sync complete. {inserted_count} new orders pulled.")

    except sqlite3.Error as e:
        logger.error(f"SQLite error during order sync: {e}")
    finally:
        conn.close()



if __name__ == "__main__":
    sync_products_to_dynamo()
    sync_orders_from_dynamo()


def retry_upload_missing_s3_urls():
    """
    Find all products that have local photos but missing S3 URLs,
    re-upload photos to S3, save the URLs, and push to DynamoDB.
    Run this manually from Pi: python3 sync.py --retry
    """
    from s3_uploader import upload_product_images

    logger.info("=" * 60)
    logger.info("Retrying S3 upload for products with missing image URLs...")

    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, name
            FROM products
            WHERE (image_url IS NULL OR image_url = '')
            AND (photo_path1 IS NOT NULL AND photo_path1 != '')
        """)
        products = cur.fetchall()

        if not products:
            logger.info("No products need re-uploading.")
            return

        logger.info(f"Found {len(products)} product(s) with missing S3 URLs.")

        for row in products:
            pid  = row['id']
            name = row['name']
            logger.info(f"  Re-uploading product ID {pid} — {name}")

            # Get local photo paths
            cur.execute(
                "SELECT photo_path1, photo_path2, photo_path3, photo_path4 FROM products WHERE id=?",
                (pid,)
            )
            paths_row = cur.fetchone()
            photo_paths = [p for p in paths_row if p] if paths_row else []

            if not photo_paths:
                logger.warning(f"  No local photos found for product {pid}, skipping.")
                continue

            # Upload to S3
            artisan_id = "0"
            urls = upload_product_images(photo_paths, artisan_id, pid)
            logger.info(f"  S3 URLs: {urls}")

            if any(urls):
                padded = (list(urls) + [None, None, None, None])[:4]
                cur.execute(
                    """UPDATE products
                       SET image_url=?, image_url_2=?, image_url_3=?, image_url_4=?,
                           sync_status='PENDING'
                       WHERE id=?""",
                    (*padded, pid)
                )
                conn.commit()
                logger.info(f"  S3 URLs saved for product {pid}.")
            else:
                logger.error(f"  S3 upload failed for product {pid}. Check AWS credentials.")

    except Exception as e:
        logger.error(f"Error during retry: {e}")
    finally:
        conn.close()

    # Now push all pending products to DynamoDB
    logger.info("Pushing updated products to DynamoDB...")
    sync_products_to_dynamo()
    logger.info("Retry complete.")


if __name__ == "__main__":
    import sys
    if "--retry" in sys.argv:
        retry_upload_missing_s3_urls()
    else:
        sync_products_to_dynamo()
        sync_orders_from_dynamo()
