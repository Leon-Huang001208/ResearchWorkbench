#!/usr/bin/env python3
"""Test Signal Lab API"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

print("Testing Signal Lab API...")

# Test 1: Get summary
print("\n1. Testing /api/signal-lab/summary...")
try:
    response = client.get("/api/signal-lab/summary")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data.get('success')}")
        if data.get('success') and data.get('summary'):
            print(f"   Summary: {data['summary']}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Get feature groups
print("\n2. Testing /api/signal-lab/features/groups...")
try:
    response = client.get("/api/signal-lab/features/groups")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data.get('success')}")
        if data.get('success') and data.get('groups'):
            print(f"   Feature groups: {list(data['groups'].keys())}")
            for key, group in data['groups'].items():
                print(f"     - {group['name']}: {len(group['features'])} features")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Get label types
print("\n3. Testing /api/signal-lab/labels/types...")
try:
    response = client.get("/api/signal-lab/labels/types")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data.get('success')}")
        if data.get('success') and data.get('label_types'):
            print(f"   Label types: {list(data['label_types'].keys())}")
except Exception as e:
    print(f"   Error: {e}")

# Test 4: Get scorers
print("\n4. Testing /api/signal-lab/scorers/types...")
try:
    response = client.get("/api/signal-lab/scorers/types")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data.get('success')}")
        if data.get('success') and data.get('scorer_types'):
            print(f"   Scorers: {list(data['scorer_types'].keys())}")
except Exception as e:
    print(f"   Error: {e}")

print("\nSignal Lab API tests completed!")
