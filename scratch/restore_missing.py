import os
import shutil

src_root = r"C:\Users\RAJATH U\.gemini\antigravity-ide\brain\12686322-1960-44ff-baa6-5232810f0989\staging\project"
dst_root = r"C:\Users\RAJATH U\Downloads\personal assitant"

restored = 0
for root, dirs, files in os.walk(src_root):
    rel = os.path.relpath(root, src_root)
    target_dir = os.path.join(dst_root, rel)
    os.makedirs(target_dir, exist_ok=True)
    for f in files:
        src_file = os.path.join(root, f)
        dst_file = os.path.join(target_dir, f)
        if not os.path.exists(dst_file):
            shutil.copy2(src_file, dst_file)
            restored += 1
            print(f"Restored: {os.path.join(rel, f)}")

print(f"Total restored missing files: {restored}")
