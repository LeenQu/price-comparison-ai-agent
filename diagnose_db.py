"""
Diagnostic-only script. Does not create, drop, or modify anything.
Run this exactly like you'd run test_noon.py:

    python diagnose_db.py

It uses the SAME engine/DATABASE_URL your app uses, and prints
exactly what that connection sees, so we can find the mismatch.
"""

from database.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    db_name = conn.execute(text("SELECT current_database()")).scalar()
    user = conn.execute(text("SELECT current_user")).scalar()
    search_path = conn.execute(text("SHOW search_path")).scalar()
    server_addr = conn.execute(text("SELECT inet_server_addr()")).scalar()
    server_port = conn.execute(text("SELECT inet_server_port()")).scalar()

    print("=" * 50)
    print(f"Connected as user   : {user}")
    print(f"Connected to database: {db_name}")
    print(f"search_path          : {search_path}")
    print(f"Server address:port  : {server_addr}:{server_port}")
    print("=" * 50)

    print("\nAll tables visible to this connection (any schema):")
    rows = conn.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
    """)).fetchall()

    if not rows:
        print("  (none found)")
    for schema, table in rows:
        print(f"  - {schema}.{table}")

    print("\nDATABASE_URL engine is using:")
    print(f"  {engine.url}")