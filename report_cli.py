#!/usr/bin/env python3
"""
研报生成命令行工具
使用方式：
python report_cli.py generate <资产代码> [--type <full/summary/valuation>] [--output <文件路径>]
"""
import argparse
import asyncio
from datetime import datetime

from core.services.report_generator import ReportGenerator


async def generate_report_cmd(canonical_id: str, report_type: str, output: str = None):
    """生成研报命令"""
    print(f"📝 正在生成{canonical_id}的{report_type}报告...")
    generator = ReportGenerator()
    report = await generator.generate(canonical_id, report_type, datetime.now())

    content = report["content"]

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 报告已保存到：{output}")
    else:
        print("\n" + "=" * 80)
        print(content)
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="AlphaFoundry研报生成工具")
    subparsers = parser.add_subparsers(dest="command")

    # 生成报告命令
    generate_parser = subparsers.add_parser("generate", help="生成资产研报")
    generate_parser.add_argument("canonical_id", help="资产代码，如600000")
    generate_parser.add_argument(
        "--type", choices=["full", "summary", "valuation"], default="full", help="报告类型"
    )
    generate_parser.add_argument("--output", help="输出文件路径，不指定则打印到控制台")

    args = parser.parse_args()

    if args.command == "generate":
        asyncio.run(generate_report_cmd(args.canonical_id, args.type, args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
