#!/usr/bin/env python3
"""Test Memory & Learning module integration."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient

from app.api.main import app
from core.services.closed_loop_service import ClosedLoopService

client = TestClient(app)


print("=" * 60)
print("Testing Memory & Learning Module")
print("=" * 60)


# Test 1: Run closed loop to generate data
print("\n1. Running closed loop to generate market episodes...")
try:
    service = ClosedLoopService()
    summary = service.run_full_loop()
    print("   ✓ Closed loop completed successfully")
    print(f"   - Signals generated: {summary['signals_generated']}")
    print(f"   - Signals backtested: {summary['signals_backtested']}")
    print(f"   - Episodes recorded: {summary['episodes_recorded']}")
    print(f"   - Avg return: {summary['avg_return']:.2%}")
    if summary.get("learning_insights"):
        print(f"   - Learning insights: {len(summary['learning_insights'])} found")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback

    traceback.print_exc()


# Test 2: Test memory API - list episodes
print("\n2. Testing memory API - list episodes...")
try:
    response = client.get("/api/memory/episodes")
    print(f"   ✓ API returned {response.status_code} status")
    if response.status_code == 200:
        episodes = response.json()
        print(f"   - Found {len(episodes)} market episodes")
        if episodes:
            print(
                f"   - First episode: event_type={episodes[0]['event_type']}, return={episodes[0]['outcome_return']:.2%}"
            )
except Exception as e:
    print(f"   ✗ Failed: {e}")


# Test 3: Test pattern API - refresh patterns
print("\n3. Testing pattern API - refresh patterns...")
try:
    response = client.get("/api/memory/patterns/refresh")
    print(f"   ✓ API returned {response.status_code} status")
    if response.status_code == 200:
        data = response.json()
        print(f"   - Learned from {data['episodes_learned']} episodes")
except Exception as e:
    print(f"   ✗ Failed: {e}")


# Test 4: Test pattern API - get event type pattern
print("\n4. Testing pattern API - get event type pattern...")
try:
    # Get list of event types from episodes
    episodes_response = client.get("/api/memory/episodes")
    if episodes_response.status_code == 200:
        episodes = episodes_response.json()
        if episodes:
            event_type = episodes[0]["event_type"]
            response = client.get(f"/api/memory/patterns/event-type/{event_type}")
            print(f"   ✓ API returned {response.status_code} status")
            if response.status_code == 200:
                pattern = response.json()
                if pattern:
                    print(f"   - Event type: {event_type}")
                    print(f"   - Win rate: {pattern['win_rate']:.1%}")
                    print(f"   - Avg excess return: {pattern['average_excess_return']:.2%}")
                    print(f"   - Sample size: {pattern['sample_size']}")
                else:
                    print(f"   - No pattern data for event type: {event_type}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback

    traceback.print_exc()


# Test 5: Test pattern API - get recommendation
print("\n5. Testing pattern API - get recommendation...")
try:
    # Get an event type
    episodes_response = client.get("/api/memory/episodes")
    if episodes_response.status_code == 200:
        episodes = episodes_response.json()
        if episodes:
            event_type = episodes[0]["event_type"]
            response = client.get(f"/api/memory/patterns/recommend?event_type={event_type}")
            print(f"   ✓ API returned {response.status_code} status")
            if response.status_code == 200:
                rec = response.json()
                print(f"   - Should trade: {rec['should_trade']}")
                print(f"   - Confidence: {rec['confidence']:.1%}")
                print(f"   - Reason: {rec['reason']}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback

    traceback.print_exc()


print("\n" + "=" * 60)
print("Memory & Learning module test completed!")
print("=" * 60)
