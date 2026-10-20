import os

def examine(folder):
    print(f"=== {folder} ===")
    for item in os.listdir(folder):
        p = os.path.join(folder, item)
        if os.path.isdir(p):
            total_size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
            count = sum(len(fs) for _, _, fs in os.walk(p))
            print(f"  [DIR]  {item:<25} {total_size/(1024*1024):>8.2f} MB ({count} files)")
        else:
            sz = os.path.getsize(p)
            print(f"  [FILE] {item:<25} {sz/(1024*1024):>8.2f} MB")

for f in ['frontend', 'storage', 'logs', 'dist', 'artifacts']:
    if os.path.exists(f):
        examine(f)
