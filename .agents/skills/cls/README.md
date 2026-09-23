# CLS News - 财联社新闻爬虫 (仅 CLI 版本)

爬取财联社电报新闻，支持关键词过滤。**仅支持 CLI 命令行调用**。

## 简介

CLS News 是一个专业的财联社新闻爬虫，帮助用户快速获取指定时间范围内的财经新闻，支持关键词筛选，最终输出结构化的 JSON 报告。

## 功能特性

- **日期范围爬取** - 支持自定义起止日期，灵活获取历史数据
- **关键词过滤** - 按关键词筛选相关新闻，支持多关键词
- **时间分布分析** - 按 3 小时时段统计新闻发布规律
- **JSON 格式输出** - 输出结构化 JSON 数据
- **持久化去重** - 记录已获取的电报，避免重复处理

## 快速开始

### 安装依赖

```bash
pip install requests
```

### 使用方式（仅 CLI）

```bash
# 基本使用（爬取最近2天）
python scripts/cls.py

# 指定日期范围
python scripts/cls.py --start_date 2026-04-01 --end_date 2026-04-15

# 使用关键词过滤
python scripts/cls.py --keywords "半导体,AI"

# 启用持久化去重
python scripts/cls.py --state_path ./state/cls_telegrams.json
```

## CLI 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--start_date` | 起始日期 (YYYY-MM-DD) | - |
| `--end_date` | 结束日期 (YYYY-MM-DD) | - |
| `--days` | 默认爬取天数 | 2 |
| `--keywords` | 关键词列表，逗号分隔 | - |
| `--output_dir` | 输出目录 | ./output |
| `--state_path` | 状态文件路径，用于持久化去重 | - |
| `--skip_existing` | 是否跳过已存在的电报 | true |
| `--start_hour` | 起始小时 (0-23) | - |
| `--end_hour` | 结束小时 (0-23) | - |
| `--delay` | 基础请求延迟（秒） | 1.5 |
| `--max_pages` | 最大爬取页数 | 150 |
| `--verbose` | 显示详细日志 | true |

## 注意事项

- 请合理设置爬取频率，避免对服务器造成压力
- 建议单次爬取日期范围不超过 30 天
- 仅支持 CLI 命令行调用，不支持编程接口或 Claude Code Skill 调用

## 详细文档

请参阅 [SKILL.md](SKILL.md) 获取完整文档。

## 许可证

本项目采用 CC BY-NC-SA 4.0 许可证。
