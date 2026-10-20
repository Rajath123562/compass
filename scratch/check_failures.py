import json
import sqlite3

con = sqlite3.connect("storage/compass.db")
cur = con.cursor()
cur.execute("SELECT payload FROM task_events WHERE event_type='task_failed' ORDER BY id DESC LIMIT 20")
rows = cur.fetchall()
reasons = [json.loads(r[0]).get("reason", "") for r in rows]
print(json.dumps(reasons, indent=2))
