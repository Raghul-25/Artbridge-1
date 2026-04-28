import time
import threading
import uuid
import datetime
from db import get_connection
import dynamodb

def is_connected():
    """Simple check if AWS DynamoDB is reachable."""
    try:
        dynamodb.get_dynamo_resource().meta.client.describe_limits()
        return True
    except Exception:
        return False

def push_orders():
    """Push pending orders from local SQLite to DynamoDB."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM orders WHERE sync_status = 'PENDING'")
    pending_orders = cur.fetchall()
    
    for row in pending_orders:
        order_dict = dict(row)
        
        # Ensure we have a string ID for DynamoDB
        dynamo_id = order_dict.get('dynamo_id')
        if not dynamo_id:
            dynamo_id = f"order_{uuid.uuid4().hex[:8]}"
            cur.execute("UPDATE orders SET dynamo_id = ? WHERE id = ?", (dynamo_id, order_dict['id']))
            conn.commit()
            
        dynamo_order = {
            "id": dynamo_id,
            "product_id": str(order_dict.get("product_id", "")),
            "artisan_id": str(order_dict.get("artisan_id", "")),
            "customer_name": order_dict.get("buyer", "Customer"),
            "address": order_dict.get("address", "N/A"),
            "status": order_dict.get("status", "PLACED"),
            "payment_status": order_dict.get("payment_status", "PENDING"),
            "tracking": order_dict.get("tracking", ""),
            "created_at": order_dict.get("last_updated", datetime.datetime.utcnow().isoformat())
        }
        
        success = dynamodb.push_order_to_dynamo(dynamo_order)
        if success:
            cur.execute("UPDATE orders SET sync_status = 'SYNCED' WHERE id = ?", (order_dict['id'],))
            conn.commit()
            print(f"[Sync] Pushed order {dynamo_id} to DynamoDB.")

    conn.close()

def pull_orders():
    """Pull new orders from DynamoDB to local SQLite."""
    dynamo_orders = dynamodb.fetch_all_orders_from_dynamo()
    
    conn = get_connection()
    cur = conn.cursor()
    
    for d_order in dynamo_orders:
        dynamo_id = d_order.get("id")
        if not dynamo_id:
            continue
            
        # Check if it already exists locally
        cur.execute("SELECT id FROM orders WHERE dynamo_id = ?", (dynamo_id,))
        if cur.fetchone():
            continue
            
        # Insert missing order from cloud
        cur.execute(
            """
            INSERT INTO orders (product_id, artisan_id, buyer, status, tracking, payment_status, address, sync_status, dynamo_id, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d_order.get("product_id"),
                d_order.get("artisan_id"),
                d_order.get("customer_name", "Customer"),
                d_order.get("status", "PLACED"),
                d_order.get("tracking", "N/A"),
                d_order.get("payment_status", "PENDING"),
                d_order.get("address", "N/A"),
                "SYNCED",
                dynamo_id,
                d_order.get("created_at", datetime.datetime.utcnow().isoformat())
            )
        )
        conn.commit()
        print(f"[Sync] Pulled order {dynamo_id} from DynamoDB.")
        
    conn.close()

def sync_loop():
    """Continuous loop checking internet and syncing."""
    while True:
        try:
            if is_connected():
                push_orders()
                pull_orders()
        except Exception as e:
            print(f"[Sync Worker] Error during sync: {e}")
        time.sleep(30) # Run every 30 seconds

def start_sync_thread():
    """Starts the sync worker as a background daemon thread."""
    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
    print("[Sync Worker] Started background offline-first sync thread.")
