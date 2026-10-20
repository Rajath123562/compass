import os
import sqlite3
import zipfile

# check compressed size of compass.db
with zipfile.ZipFile('scratch/test_db_zip.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    z.write('storage/compass.db', 'compass.db')

sz_zip = os.path.getsize('scratch/test_db_zip.zip')
print(f"Compressed compass.db size: {sz_zip / (1024*1024):.2f} MB")
