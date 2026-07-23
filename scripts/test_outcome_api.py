#!/usr/bin/env python3
"""Test outcome API endpoint directly to see the full error."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

print("Testing /api/outcomes/aggregate/list...")
try:
    response = client.get("/api/outcomes/aggregate/list")
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
    else:
        print(f"Success! Got {len(response.json())} outcomes.")
except Exception as e:
    import traceback

    print(f"Exception: {e}")
    traceback.print_exc()
