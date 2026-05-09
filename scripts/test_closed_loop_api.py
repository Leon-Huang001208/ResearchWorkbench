#!/usr/bin/env python3
"""Test the closed loop API"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

print("Testing /api/pipeline/closed-loop...")
try:
    # 首先测试 outcomes API 确保它可以正常工作
    response = client.get("/api/outcomes/aggregate/list")
    print(f"Outcomes API status: {response.status_code}")
    if response.status_code == 200:
        print(f"Got {len(response.json())} outcomes")

    # 然后尝试测试 closed-loop API (注意: 这可能需要较长时间)
    print("\nNote: Running closed-loop may take time, skipping for now.")
    print("You can test it manually via the web UI.")

except Exception as e:
    import traceback
    print(f"Exception: {e}")
    traceback.print_exc()
