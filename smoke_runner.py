#!/usr/bin/env python3
"""
AlphaFoundry 端到端MVP一键冒烟测试脚本
使用方式：python smoke_runner.py
所有测试通过返回0，失败返回1
"""
import subprocess
import sys
import time

import requests


def run_command(cmd: str, cwd: str = None) -> tuple[int, str, str]:
    """执行shell命令，返回返回码、stdout、stderr"""
    proc = subprocess.Popen(
        cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout, stderr


def test_smoke() -> bool:
    print("🚀 开始AlphaFoundry端到端冒烟测试...")

    # 1. 检查依赖是否安装
    print("\n📋 1. 检查依赖安装...")
    code, _, _ = run_command("pip list | grep fastapi")
    if code != 0:
        print("❌ 依赖未安装，请先运行pip install -r requirements.txt")
        return False

    # 2. 启动服务
    print("\n🔧 2. 启动API服务...")
    proc = subprocess.Popen(
        "uvicorn app.api.main:app --port 8001",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(5)

    try:
        # 3. 测试健康检查接口
        print("\n🩺 3. 测试健康检查接口...")
        try:
            resp = requests.get("http://127.0.0.1:8001/health", timeout=5)
            if resp.status_code != 200:
                print(f"❌ 健康检查失败，状态码：{resp.status_code}")
                return False
            print("✅ 健康检查接口正常")
        except Exception as e:
            print(f"❌ 健康检查请求失败：{e}")
            return False

        # 4. 测试资产分析接口
        print("\n📊 4. 测试资产分析接口...")
        try:
            resp = requests.post(
                "http://127.0.0.1:8001/api/assets/analyze",
                json={"canonical_id": "600000"},
                timeout=10,
            )
            if resp.status_code != 200:
                print(f"❌ 资产分析接口失败，状态码：{resp.status_code}")
                return False
            data = resp.json()
            if (
                data.get("canonical_id") != "600000"
                or data.get("price_volume", {}).get("close_price") is None
            ):
                print("❌ 资产分析返回数据不完整")
                return False
            print("✅ 资产分析接口正常，自动降级逻辑生效")
        except Exception as e:
            print(f"❌ 资产分析请求失败：{e}")
            return False

        # 5. 测试首页访问
        print("\n🌐 5. 测试前端页面访问...")
        try:
            resp = requests.get("http://127.0.0.1:8001/", timeout=5)
            if resp.status_code != 200 or "AlphaFoundry" not in resp.text:
                print("❌ 首页访问失败")
                return False
            print("✅ 前端页面正常")
        except Exception as e:
            print(f"❌ 首页访问请求失败：{e}")
            return False

        print("\n🎉 所有冒烟测试通过！✅")
        return True
    finally:
        # 停止服务
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    success = test_smoke()
    sys.exit(0 if success else 1)
