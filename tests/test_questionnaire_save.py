import json
import os
from pathlib import Path

TEST_DIR = Path("trajectories/test_config/test_user/Post_experiment")
TEST_DIR.mkdir(parents=True, exist_ok=True)
FILE = TEST_DIR / "testuser_0_preference.json"

first = {"value": 1}
second = {"value": 2}

# Cleanup
if FILE.exists():
    FILE.unlink()

# Simulate first write (should create file)
if FILE.exists():
    print("FAIL: file exists before first write")
else:
    with open(FILE, 'w', encoding='utf-8') as f:
        json.dump(first, f)

# Simulate second write guarded by existence check
if FILE.exists():
    print("Second write: file exists, skipping write (expected)")
else:
    with open(FILE, 'w', encoding='utf-8') as f:
        json.dump(second, f)

# Verify content is the first
with open(FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

if data == first:
    print("PASS: first submission preserved")
else:
    print("FAIL: file content was overwritten", data)
