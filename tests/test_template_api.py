#!/usr/bin/env python3
"""测试模板管理API"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from io import BytesIO

import httpx


async def test_templates_api():
    """测试模板管理API"""
    base_url = "http://127.0.0.1:8000"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Test health endpoint
        print("Testing health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"Health response: {response.status_code}")
        print(f"Health response data: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

        # 2. Test list templates endpoint
        print("\nTesting list templates endpoint...")
        try:
            response = await client.get(f"{base_url}/api/templates/")
            print(f"List templates status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Found {data.get('total', 0)} template(s)")
                for tmpl in data.get('templates', []):
                    print(f"  - {tmpl['template_name']}: {tmpl['description']}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error listing templates: {e}")
            import traceback
            traceback.print_exc()

        # 3. Try to create a YAML template (without file upload)
        print("\nTesting create YAML template...")
        try:
            response = await client.post(
                f"{base_url}/api/templates/create-yaml",
                data={
                    "template_name": "test_report",
                    "description": "测试报告模板",
                    "version": "1.0",
                },
            )
            print(f"Create YAML template status: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error creating YAML template: {e}")

        # 4. List templates again
        print("\nListing templates again...")
        try:
            response = await client.get(f"{base_url}/api/templates/")
            if response.status_code == 200:
                data = response.json()
                print(f"Now have {data.get('total', 0)} template(s)")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_templates_api())
