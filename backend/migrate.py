import sqlite3, os

db_path = os.path.join(os.path.dirname(os.path.abspath("backend/db.py")), "artbridge.db")
print("DB path:", db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

commands = [
    "ALTER TABLE products ADD COLUMN sync_status TEXT DEFAULT 'PENDING'",
    "ALTER TABLE products ADD COLUMN last_updated TEXT",
    "ALTER TABLE orders ADD COLUMN sync_status TEXT DEFAULT 'PENDING'",
    "ALTER TABLE orders ADD COLUMN last_updated TEXT",
]

for cmd in commands:
    try:
        cur.execute(cmd)
        print("OK:", cmd)
    except Exception as e:
        print("SKIP:", e)

conn.commit()
conn.close()
print("Done.")
