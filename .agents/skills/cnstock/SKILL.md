---
name: cnstock
description: Use when maintaining or manually running the ResearchWorkbench legacy CNStock crawler; not as proof that the current Research Web DataHub provider is callable.
license: LICENSE-CC-BY-NC-SA 4.0 in LICENSE.txt
author: Skill Forge
---

# cnstock - 中国证券网爬取技能

本 Skill 只覆盖项目内 legacy crawler。当前 Research Web 是否可调用中国证券网来源，必须以 DataHub Provider 状态、合同测试和真实验收为准。

## 更新记录

### 2026-04-27 API 路径修复
- **问题**：API 返回 `{"code":10304,"desc":"未登录"}`
- **修复**：
  - 新闻列表 API：`/www/news_list/channelNewsList` → `/www/newsList/channelNewsList` (下划线改驼峰)
  - 搜索 API：路径保持 `/search/news`，但需要 `cnstock-client-type: 01` 请求头（代码已包含）
- **验证**：两个 API 现在都可以正常获取数据

Use when you need to crawl and analyze financial news from China Securities Journal website

## 功能特点

- 爬取中国证券网新闻标题、链接、发布时间
- 支持按日期范围筛选新闻
- 关键词过滤功能
- 支持获取文章正文内容
- 结果保存为 JSON 格式
- 反爬策略（请求间隔、User-Agent 轮换、WAF 冷却）
- 指数退避重试机制
- **日志记录功能** - 支持同时输出到控制台和文件，日志轮转

## 使用场景

- 需要收集中国证券市场新闻资讯
- 按时间范围筛选历史新闻
- 关键词过滤感兴趣的财经新闻
- 批量导出新闻数据用于分析
- 获取新闻正文内容

## 前置条件

- Python 3.7+
- requests 库

## 工作流

1. **初始化配置** - 设置爬取参数（日期范围、关键词、输出路径）
2. **构建请求** - 生成目标 URL，设置请求头
3. **发送请求** - 带反爬策略的 HTTP 请求
4. **解析页面** - 提取新闻标题、链接、发布时间
5. **过滤筛选** - 按日期和关键词过滤
6. **获取正文** - 可选获取文章正文内容
7. **保存结果** - 输出为 JSON 格式

## 输入参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `start_date` | string | 是 | - | 开始日期，格式：YYYY-MM-DD |
| `end_date` | string | 是 | - | 结束日期，格式：YYYY-MM-DD |
| `keywords` | list | 否 | [] | 关键词列表，用于过滤新闻标题 |
| `output_path` | string | 否 | "./output" | 输出目录路径 |
| `max_pages` | int | 否 | 5 | 最大爬取页数 |
| `delay` | float | 否 | 1.0 | 请求间隔（秒） |
| `verbose` | boolean | 否 | true | 是否显示详细日志 |
| `channel` | string/list | 否 | "证券" | 新闻频道名称（单个或列表：快讯/时政/公司/产经/金融/证券） |
| `node_id` | string | 否 | "10232" | 新闻频道节点ID（可选，与 channel 二选一） |
| `all_channels` | boolean | 否 | false | 是否爬取所有频道（为 true 时忽略 channel/node_id） |
| `page_size` | int | 否 | 32 | 每页新闻数量 |
| `fetch_content` | boolean | 否 | false | 是否获取文章正文内容 |
| `log_file` | string | 否 | None | 日志文件路径，None 表示不写入文件 |
| `log_level` | string | 否 | "INFO" | 日志级别: DEBUG, INFO, WARNING, ERROR |
| `state_path` | string | 否 | None | 状态文件路径，用于持久化去重，None 表示不启用 |
| `skip_existing` | boolean | 否 | true | 是否跳过已存在的新闻（仅当 state_path 提供时有效） |

### node_id 说明

| node_id | 说明 |
|---------|------|
| 10004 | 快讯 |
| 10005 | 时政 |
| 10006 | 公司 |
| 10007 | 产经 |
| 10011 | 金融 |
| 10232 | 证券（默认） |

## 输出格式

```python
{
    "success": True/False,
    "news_count": 15,
    "news_list": [
        {
            "title": "新闻标题",
            "url": "https://...",
            "date": "2024-01-15",
            "categories": ["产经", "金融"],  // 新闻所属的频道列表
            "content": "文章正文内容..."
        }
    ],
    "keywords": [],
    "output_file": "C:\\path\\to\\news_20240115.json",
    "stats": {
        "success_count": 10,
        "failure_count": 5
    },
    "errors": []
}
```

## 使用示例

### 示例 1：基本使用 - 爬取指定日期范围的新闻

```python
from cnstock import main

result = main(
    start_date="2024-01-01",
    end_date="2024-01-15"
)
print(f"爬取完成，共获取 {result['news_count']} 条新闻")
```

### 示例 2：指定日期范围和关键词

```python
from cnstock import main

result = main(
    start_date="2024-01-01",
    end_date="2024-01-15",
    keywords=["人工智能", "芯片", "新能源"],
    max_pages=20
)
```

### 示例 3：获取多个频道的新闻

```python
from cnstock import main

# 爬取产经和金融两个频道
result = main(
    start_date="2024-01-01",
    end_date="2024-01-15",
    channel=["产经", "金融"],
    max_pages=1
)

# 新闻会自动去重，重复新闻的 categories 会合并
for news in result['news_list']:
    print(f"{news['title']} - 频道: {news['categories']}")
```

### 示例 4：爬取所有频道

```python
from cnstock import main

# 爬取全部6个频道（快讯/时政/公司/产经/金融/证券）
result = main(
    start_date="2024-01-01",
    end_date="2024-01-15",
    all_channels=True,
    max_pages=1
)
```

### 示例 5：获取文章正文内容

```python
from cnstock import main

result = main(
    start_date="2024-01-01",
    end_date="2024-01-15",
    channel="证券",
    max_pages=1,
    page_size=5,
    fetch_content=True
)
```

### 示例 6：使用日志记录功能

```python
from cnstock import main

# 启用日志记录到文件
result = main(
    start_date="2024-01-01",
    end_date="2024-01-15",
    channel="证券",
    max_pages=1,
    log_file="./logs/cnstock.log",  # 日志文件路径
    log_level="INFO"  # 日志级别
)
```

### 示例 7：在 Codex 中使用

```
/cnstock --start_date 2024-01-01 --end_date 2024-01-15 --keywords "人工智能"
/cnstock --start_date 2024-01-01 --end_date 2024-01-15 --channel "产经" --fetch_content true
```

### 示例 8：使用持久化去重

```python
from cnstock import main

# 启用持久化去重，避免重复爬取相同新闻
result = main(
    start_date="2024-01-01",
    end_date="2024-01-15",
    channel="证券",
    max_pages=1,
    state_path="./data/cnstock_state.json",  # 状态文件路径
    skip_existing=True  # 跳过已存在的新闻
)
```

### 示例 9：使用 CLI 接口

```bash
# 基本使用
python cnstock.py --start-date 2024-01-01 --end-date 2024-01-15

# 使用关键词
python cnstock.py --start-date 2024-01-01 --keywords "人工智能,芯片"

# 指定频道
python cnstock.py --start-date 2024-01-01 --channel "证券,产经"

# 爬取所有频道并获取正文
python cnstock.py --start-date 2024-01-01 --all-channels --fetch-content

# 输出 JSON 到标准输出（供其他程序调用）
python cnstock.py --start-date 2024-01-01 --print-json

# 使用日志文件
python cnstock.py --start-date 2024-01-01 --log-file ./logs/cnstock.log --log-level DEBUG

# 持久化去重
python cnstock.py --start-date 2024-01-01 --state-path ./data/state.json

# 安静模式（不输出详细日志）
python cnstock.py --start-date 2024-01-01 --quiet

# 查看帮助
python cnstock.py --help
```

## CLI 参数说明

| 参数 | 说明 | 默认值 |
|-----|------|-------|
| `--start-date` | 开始日期 (YYYY-MM-DD) | **必需** |
| `--end-date` | 结束日期 (YYYY-MM-DD) | 同开始日期 |
| `--keywords` | 关键词，多个用逗号分隔 | - |
| `--output-path` | 输出目录路径 | `./output` |
| `--max-pages` | 最大爬取页数 | 5 |
| `--delay` | 请求间隔秒数 | 1.0 |
| `--node-id` | 新闻频道节点ID | 10232 |
| `--channel` | 新闻频道名称，多个用逗号分隔 | - |
| `--all-channels` | 爬取所有频道 | False |
| `--page-size` | 每页新闻数量 | 32 |
| `--fetch-content` | 获取文章正文内容 | False |
| `--quiet` | 关闭详细日志输出 | False |
| `--log-file` | 日志文件路径 | - |
| `--log-level` | 日志级别 (DEBUG/INFO/WARNING/ERROR) | INFO |
| `--state-path` | 状态文件路径（持久化去重） | - |
| `--no-skip-existing` | 不跳过已存在的新闻 | False |
| `--print-json` | 将结果以 JSON 格式打印到 stdout | False |

## WAF 防护说明

中国证券网使用阿里云 WAF 防护，爬虫会自动处理：

- **自动冷却**：连续触发 WAF 后会自动暂停（60-300秒）
- **指数退避重试**：请求失败后自动重试，等待时间递增
- **User-Agent 轮换**：随机使用不同的浏览器标识
- **请求头随机化**：sec-ch-ua 等 header 随机变化

## 注意事项

- 请遵守网站 robots.txt 规则
- 合理设置请求间隔，避免对服务器造成压力
- 仅用于个人学习和研究目的
- 请勿将爬取的数据用于商业用途
- 网站结构可能变化，需定期维护选择器
- 获取文章正文时，建议使用较小的 page_size 以避免触发 WAF

## 错误处理

| 错误类型 | 可能原因 | 处理方式 |
|---------|---------|---------|
| 网络请求失败 | 网络连接问题、IP 被封 | 检查网络，增加延迟，使用代理 |
| WAF 防护触发 | 请求频率过高 | 自动冷却，等待后重试 |
| 页面解析失败 | 网站结构更新 | 更新选择器 |
| 日期解析错误 | 日期格式不正确 | 使用 YYYY-MM-DD 格式 |
| 文件写入失败 | 输出目录无权限 | 检查输出目录权限 |

---

## 合理化借口对照表

| 借口 | 现实 |
|------|------|
| "我先手动试一下，之后再加测试" | 没有测试 = 没有技能。删除代码，先写测试。 |
| "这个爬取很简单，不需要测试" | 简单的代码也会出问题。测试定义预期行为。 |
| "我已经手动测试过了" | 手动测试无法防止回归。测试是文档。 |

## 红旗警告 - 立即停止

- **"我先手动试一下"**
  → STOP - 先写测试，定义预期行为。

- **"这个很简单"**
  → STOP - 简单不等于正确。写测试。

- **"我已经手动测试过了"**
  → STOP - 手动测试不能替代自动化测试。

## 铁律

**NO SKILL WITHOUT A FAILING TEST FIRST**

- 先写技能再测试？删除它，重新开始。
- 编辑技能但没有测试？同样违规。
- 没有例外。
