import os

stray_files = ['$null', '0]', '6}', '{p.name()}', 'frontend/{', 'scratch/test_db_zip.zip', 'scratch/vacuum_test.db']
for f in stray_files:
    if os.path.exists(f):
        try:
            os.remove(f)
            print(f"Removed: {f}")
        except Exception as e:
            print(f"Error removing {f}: {e}")
