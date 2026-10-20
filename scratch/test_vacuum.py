import sqlite3
import os

con = sqlite3.connect('storage/compass.db')
cur = con.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for (t,) in tables:
    count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"Table {t}: {count} rows")

# Check if vacuuming creates a much smaller database
con.close()
# Copy to temp and vacuum
import shutil
shutil.copy('storage/compass.db', 'scratch/vacuum_test.db')
con2 = sqlite3.connect('scratch/vacuum_test.db')
con2.execute('VACUUM')
con2.close()
sz_orig = os.path.getsize('storage/compass.db')
sz_vac = os.path.getsize('scratch/vacuum_test.db')
print(f"Original DB: {sz_orig / (1024*1024):.2f} MB")
print(f"Vacuumed DB: {sz_vac / (1024*1024):.2f} MB")
