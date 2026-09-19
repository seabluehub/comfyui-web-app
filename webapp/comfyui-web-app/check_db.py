import sqlite3, json
conn = sqlite3.connect('data/comfyui_web.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)
conn.row_factory = sqlite3.Row
for t in tables:
    name = t[0]
    rows = conn.execute(f"SELECT * FROM [{name}] LIMIT 3").fetchall()
    print(f"\n--- {name} ({len(rows)} sample rows) ---")
    for r in rows:
        print(dict(r))
conn.close()
