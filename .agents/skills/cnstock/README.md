# cnstock - 中国证券网爬取技能

Use when you need to crawl and analyze financial news from China Securities Journal website

## 版本

0.1.0

## 作者

Skill Forge

## 功能介绍

cnstock 是一个专业的中国证券网新闻爬取工具，支持按日期范围筛选、关键词过滤、结果导出等功能。

### 主要功能

- 新闻爬取：获取标题、链接、发布时间
- 日期筛选：支持自定义开始/结束日期
- 关键词过滤：按关键词筛选新闻标题
- 反爬策略：请求间隔、User-Agent 轮换
- 结果导出：JSON 格式保存

## 安装依赖

```bash
pip install requests beautifulsoup4 lxml
```

## 使用

### 在 Claude Code 中使用

```
/cnstock --start_date 2024-01-01 --keywords "人工智能"
```

### 作为 Python 模块使用

```python
from cnstock import main

result = main(
    start_date="2024-01-01",
    end_date="2024-01-15",
    keywords=["人工智能", "芯片"],
    max_pages=10
)

print(f"爬取了 {result['news_count']} 条新闻")
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--start_date` | 开始日期 (YYYY-MM-DD) | 7天前 |
| `--end_date` | 结束日期 (YYYY-MM-DD) | 今天 |
| `--keywords` | 关键词列表（逗号分隔） | - |
| `--max_pages` | 最大爬取页数 | 10 |
| `--delay` | 请求间隔（秒） | 1.0 |
| `--output_path` | 输出目录 | ./output |
| `--verbose` | 显示详细日志 | true |

## 自动生成

此技能由 Skill Forge 自动生成。
