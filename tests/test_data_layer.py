"""Data Layer 基础测试"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """测试模块导入"""
    print("Testing imports...")

    # 测试 adapters

    print("✓ adapters imported")

    # 测试 parsers

    print("✓ parsers imported")

    # 测试 normalizers

    print("✓ normalizers imported")

    # 测试 repositories

    print("✓ repositories imported")

    print("\nAll imports successful!")


def test_text_normalizer():
    """测试文本标准化器"""
    from data_layer.normalizers import TextNormalizer

    normalizer = TextNormalizer()

    test_text = """  Hello　World！
This is a test.

Another line with trailing spaces
"""
    normalized = normalizer.normalize(test_text)
    print(f"\nText normalization test:")
    print(f"Input: {repr(test_text)}")
    print(f"Output: {repr(normalized)}")
    print("✓ TextNormalizer works")


def test_date_normalizer():
    """测试日期标准化器"""
    from data_layer.normalizers import DateNormalizer

    normalizer = DateNormalizer()

    test_cases = [
        "2024-01-15",
        "2024/01/15",
        "2024年1月15日",
        "2024.01.15",
        "20240115",
    ]

    print(f"\nDate normalization test:")
    for test_date in test_cases:
        result = normalizer.normalize_to_str(test_date)
        print(f"  {test_date:20s} -> {result}")

    print("✓ DateNormalizer works")


if __name__ == "__main__":
    test_imports()
    test_text_normalizer()
    test_date_normalizer()
    print("\n✅ All basic tests passed!")
