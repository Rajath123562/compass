import os
import re

def main():
    pattern = re.compile(r'(?:os\.environ\.get|os\.getenv|os\.environ\[)\s*\(?\s*[\'"]([A-Za-z0-9_]+)[\'"]')
    found = set()
    for root, dirs, files in os.walk('.'):
        if any(ignored in root for ignored in ['.git', 'node_modules', '.venv', '__pycache__', 'dist']):
            continue
        for f in files:
            if f.endswith(('.py', '.js', '.jsx', '.ts', '.tsx')):
                p = os.path.join(root, f)
                try:
                    with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.read()
                        matches = pattern.findall(content)
                        found.update(matches)
                except Exception:
                    pass
    print("Found environment variables:")
    for var in sorted(found):
        print(f"  {var}")

if __name__ == '__main__':
    main()
