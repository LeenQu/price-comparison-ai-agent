from database.connection import engine

try:
    conn = engine.connect()
    print("✅ Connected to PostgreSQL!")
    conn.close()
except Exception as e:
    print("❌ Error:", e)