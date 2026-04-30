import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiosk.db")

def cleanup_db():
    print(f"Cleaning up database: {DB_PATH}")
    
    keep_ids = (6, 8, 11, 17)
    
    # We need to format the tuple for the SQL query correctly
    placeholders = ",".join("?" * len(keep_ids))
    
    try:
        # We don't use the wrapper here so we have direct control
        with sqlite3.connect(DB_PATH, timeout=20) as conn:
            cur = conn.cursor()
            
            # 1. Delete dependent shipping details first
            cur.execute(f"DELETE FROM shipping_details WHERE product_id IS NOT NULL AND product_id NOT IN ({placeholders})", keep_ids)
            deleted_shipping = cur.rowcount
            
            # 2. Delete dependent orders
            cur.execute(f"DELETE FROM orders WHERE product_id IS NOT NULL AND product_id NOT IN ({placeholders})", keep_ids)
            deleted_orders = cur.rowcount
            
            # 3. Finally, delete the products themselves
            cur.execute(f"DELETE FROM products WHERE id NOT IN ({placeholders})", keep_ids)
            deleted_products = cur.rowcount
            
            conn.commit()
            
            print(f"[OK] Cleanup successful!")
            print(f"  - Deleted {deleted_products} unwanted products.")
            print(f"  - Deleted {deleted_orders} orphaned orders.")
            print(f"  - Deleted {deleted_shipping} orphaned shipping detail records.")
            print(f"Kept product IDs: {keep_ids}")
            
    except Exception as e:
        print(f"[FAIL] Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup_db()
