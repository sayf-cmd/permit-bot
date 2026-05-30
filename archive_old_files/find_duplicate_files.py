import hashlib
from pathlib import Path
from collections import defaultdict

DATA_ROOT = Path("data")

def file_hash(path):
    h = hashlib.md5()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()

files = []
for ext in ("*.xlsx", "*.xlsm"):
    files.extend(DATA_ROOT.rglob(ext))

print(f"Found files: {len(files)}")

hashes = defaultdict(list)

for path in files:
    try:
        h = file_hash(path)
        hashes[h].append(path)
    except Exception as e:
        print(f"SKIP {path}: {e}")

print("\nDUPLICATES:\n")

count = 0

for h, paths in hashes.items():
    if len(paths) > 1:
        count += 1
        print(f"\nDuplicate group #{count}:")
        for p in paths:
            print(f" - {p}")

if count == 0:
    print("No duplicate files found.")