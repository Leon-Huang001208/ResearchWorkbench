#!/usr/bin/env python3
"""调试资产分析API"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from datetime import datetime

from core.services import AssetAnalysisService
from data_layer.coordinator.multi_source_coordinator import get_coordinator


async def test_analysis_card():
    """测试生成分析卡片"""
    print("=== Testing Asset Analysis Card ===")

    service = AssetAnalysisService(coordinator=get_coordinator())

    canonical_id = "600519.SH"
    print(f"Generating analysis card for {canonical_id}...")

    try:
        card = await service.generate_analysis_card(
            canonical_id=canonical_id, as_of=datetime.utcnow()
        )

        print("\n✓ Analysis card generated!")
        print(f"  - Canonical ID: {card.canonical_id}")
        print(f"  - Current price: {card.current_price}")
        print(f"  - Price change: {card.price_change}")
        print(f"  - Price change %: {card.price_change_pct}")
        print(f"  - Price bars: {len(card.price_bars)}")
        print(f"  - Has basic info: {card.basic_info is not None}")
        print(f"  - Has financial: {card.financial is not None}")
        print(f"  - Has capital flow: {card.capital_flow is not None}")

        # 尝试序列化为JSON
        print("\n=== Testing JSON Serialization ===")
        try:
            # 使用Pydantic V2 style
            if hasattr(card, "model_dump"):
                data = card.model_dump()
            else:
                data = card.dict()

            json_str = json.dumps(data, default=str, ensure_ascii=False, indent=2)
            print(f"✓ JSON serialization successful! Length: {len(json_str)}")

            # 打印前500字符
            print(f"\nFirst 500 chars: {json_str[:500]}...")

            # 保存到文件
            output_path = project_root / "output" / "debug_analysis_card.json"
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_text(json_str, encoding="utf-8")
            print(f"\nSaved to: {output_path}")

        except Exception as e:
            print(f"✗ JSON serialization failed: {e}")
            import traceback

            traceback.print_exc()

        return card

    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("AlphaFoundry - API Debug")
    print("=" * 50)

    try:
        card = asyncio.run(test_analysis_card())

        if card:
            print("\n" + "=" * 50)
            print("✓ Test completed!")
        else:
            print("\n" + "=" * 50)
            print("✗ Test failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
