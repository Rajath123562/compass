import os

dirs = [d for d in os.listdir('.') if os.path.isdir(d)]
res = []
for d in dirs:
    total_size = 0
    count = 0
    for root, _, files in os.walk(d):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total_size += os.path.getsize(fp)
                count += 1
            except Exception:
                pass
    res.append((d, total_size / (1024 * 1024), count))

res.sort(key=lambda x: x[1], reverse=True)
for name, mb, c in res:
    print(f"{name:<25} {mb:>8.2f} MB  ({c:>5} files)")
