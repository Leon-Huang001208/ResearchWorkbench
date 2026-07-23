#!/usr/bin/env python3
"""测试所有模板相关的API端点"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ALPHAFOUNDRY_RUN_LIVE_API_TESTS") != "1",
    reason="live API smoke test requires an already-running server on 127.0.0.1:8000",
)


async def test_all_endpoints():
    """测试所有模板API端点"""
    base_url = "http://127.0.0.1:8000"

    print("=" * 60)
    print("测试模板管理API端点")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 测试列出模板
        print("\n1. 测试列出模板...")
        try:
            response = await client.get(f"{base_url}/api/templates/")
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   找到 {data.get('total', 0)} 个模板:")
                for tmpl in data.get("templates", []):
                    print(f"   - {tmpl.get('template_name')}: {tmpl.get('description')}")
                    print(
                        f"     has_docx: {tmpl.get('has_docx')}, has_pptx: {tmpl.get('has_pptx')}"
                    )
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")

        # 2. 测试获取单个模板
        print("\n2. 测试获取单个模板详情...")
        try:
            template_name = "test_report"
            response = await client.get(f"{base_url}/api/templates/{template_name}")
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   模板: {data.get('template_name')}")
                print(f"   占位符: {data.get('placeholders')}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")

        # 3. 测试发现占位符
        print("\n3. 测试发现占位符...")
        try:
            template_name = "test_report"
            response = await client.get(
                f"{base_url}/api/templates/{template_name}/placeholders/docx"
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   发现 {data.get('total', 0)} 个占位符:")
                for ph in data.get("placeholders", []):
                    print(f"   - {ph}")
            elif response.status_code == 404:
                print("   模板文件不存在 (这是预期的，因为我们只有YAML)")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")

        # 4. 测试上传一个简单的模板文件
        print("\n4. 测试上传模板文件...")
        try:
            test_file_path = Path("tests/test_template_with_placeholders.docx")
            if test_file_path.exists():
                print(f"   使用测试文件: {test_file_path}")
                with open(test_file_path, "rb") as f:
                    files = {
                        "file": (
                            "test_upload.docx",
                            f,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    }
                    data = {
                        "template_name": "test_upload",
                        "file_type": "docx",
                        "description": "测试上传的模板",
                    }
                    response = await client.post(
                        f"{base_url}/api/templates/upload", files=files, data=data
                    )
                    print(f"   状态码: {response.status_code}")
                    if response.status_code == 200:
                        print(f"   成功: {response.json()}")
                    else:
                        print(f"   错误: {response.text}")
            else:
                print(f"   测试文件不存在: {test_file_path}")
        except Exception as e:
            print(f"   异常: {e}")

        # 5. 测试渲染报告（仅占位符）
        print("\n5. 测试渲染报告...")
        try:
            payload = {
                "template_name": "test_report",
                "file_type": "docx",
                "placeholders": {"title": "测试报告", "date": "2026-05-12", "author": "测试用户"},
            }
            response = await client.post(f"{base_url}/api/templates/render", json=payload)
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   成功: report_id={data.get('report_id')}")
                print(f"   下载链接: {data.get('download_url')}")
            else:
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")

        # 6. 测试从资产渲染报告
        print("\n6. 测试从资产渲染报告...")
        try:
            payload = {
                "template_name": "test_report",
                "file_type": "docx",
                "canonical_id": "600519.SH",
                "report_type": "full",
            }
            response = await client.post(
                f"{base_url}/api/templates/render-from-asset", json=payload
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   成功: report_id={data.get('report_id')}")
            else:
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")


if __name__ == "__main__":
    asyncio.run(test_all_endpoints())
