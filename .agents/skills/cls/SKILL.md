---
name: cls
description: Use when maintaining or manually running the ResearchWorkbench legacy CLS crawler; not as proof that the current Research Web DataHub provider is callable.
license: LICENSE-CC-BY-NC-SA 4.0 in LICENSE.txt
author: Skill Forge
---

# cls - 财联社电报爬取技能 (仅 CLI 版本)

仅支持项目内 legacy CLI 调用：`python scripts/cls.py --args`。当前 Research Web 是否可调用财联社来源，必须以 DataHub Provider 状态、合同测试和真实验收为准。

## 功能特点

- 爬取财联社电报内容、发布时间、日期
- 支持按日期范围筛选电报
- 支持按小时范围筛选（如交易时间 9:00-15:00）
- 结果保存为 JSON 格式
- 反爬策略（User-Agent 轮换、随机延迟、Cookie 预热）
- 时间分布统计（按 3 小时时段统计）
- 日志文件记录（自动保存运行日志到文件）
- 持久化去重：记录已获取的电报，避免重复处理

## 使用方式

仅支持 **CLI 命令行调用**：

```bash
# 基本使用（爬取最近2天）
python scripts/cls.py

# 指定日期范围
python scripts/cls.py --start_date 2026-04-01 --end_date 2026-04-15

# 启用持久化去重
python scripts/cls.py --state_path ./state/cls_telegrams.json
```

## 前置条件

- Python 3.7+
- requests 库

## CLI 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--start_date` | string | - | 开始日期，格式：YYYY-MM-DD |
| `--end_date` | string | - | 结束日期，格式：YYYY-MM-DD |
| `--days` | int | 2 | 默认爬取天数（当未指定日期时）|
| `--start_hour` | int | - | 起始小时（0-23），用于筛选时间段 |
| `--end_hour` | int | - | 结束小时（0-23），用于筛选时间段 |
| `--output_dir` | string | ./output | 输出目录路径 |
| `--delay` | float | 1.5 | 基础请求延迟（秒）|
| `--delay_jitter` | float | 0.8 | 延迟抖动范围（秒）|
| `--max_retries` | int | 3 | 最大重试次数 |
| `--max_pages` | int | 150 | 最大爬取页数 |
| `--max_empty_pages` | int | 7 | 连续空页阈值 |
| `--log_to_file` | flag | true | 是否记录日志到文件 |
| `--log_filename` | string | - | 自定义日志文件名（可选）|
| `--state_path` | string | - | 状态文件路径，用于持久化去重 |
| `--skip_existing` | flag | true | 是否跳过已存在的电报 |
| `--verbose` | flag | true | 是否显示详细日志 |

## 反爬措施详解

### 1. User-Agent 轮换
- 预置 6 种主流浏览器 User-Agent
- 每次请求随机选择
- 包含 Chrome、Firefox、Safari、Edge

### 2. Cookie 预热
- 先访问页面获取 Cookie
- 模拟真实用户浏览行为
- 保持 Session 复用

### 3. 随机延迟
- 请求延迟：基础延迟 ± 抖动
- 页面间延迟：独立配置
- 重试延迟：随机范围
- 最小延迟 0.1 秒

### 4. 完整请求头
- 包含所有必要的浏览器头
- Referer 正确设置
- Cache-Control 禁用缓存

### 5. 错误重试机制
- 最多重试 3 次（可配置）
- 重试间隔随机
- JSON 解析失败也重试

## 注意事项

- 请遵守网站 robots.txt 规则
- 合理设置请求间隔，避免对服务器造成压力
- 仅用于个人学习和研究目的
- 请勿将爬取的数据用于商业用途
- 网站结构可能变化，需定期维护

## 技术细节

### 脚本文件
- `scripts/cls.py` - 核心爬虫（仅 CLI 版本）
- `scripts/utils/` - 通用工具模块
  - `log_utils.py` - 日志配置工具
  - `net_utils.py` - 网络请求工具（随机延迟、重试机制）
  - `date_utils.py` - 日期范围解析工具
  - `deduplication.py` - 持久化去重存储
  - `caching.py` - 缓存属性装饰器

### CLI 调用示例

```bash
# 基本使用
python scripts/cls.py

# 指定日期范围
python scripts/cls.py --start_date 2026-04-01 --end_date 2026-04-15

# 按交易时间筛选
python scripts/cls.py --start_hour 9 --end_hour 15

# 启用持久化去重
python scripts/cls.py --state_path ./state/cls_telegrams.json --skip_existing
```

### API 端点
- 页面 URL: `https://www.cls.cn/telegraph?date={date}`
- 数据 API: `https://www.cls.cn/api/sw`

### 请求参数
```json
{
  "app": "CailianpressWeb",
  "os": "web",
  "sv": "8.4.6",
  "sign": "9f8797a1f4de66c2370f7a03990d2737"
}
```

### 请求体
```json
{
  "type": "telegram",
  "keyword": "%20",
  "page": 1,
  "rn": 100,
  "date": "YYYY-MM-DD"
}
```

## 更新日志

- **v5.0.0** - API 适配更新
  - 适配财联社 API 变更：使用 "%20" 作为 keyword 参数绕过非空校验
  - 更新响应解析：使用新的 errno 字段代替 code，data 字段包含数据
  - 更新内容提取：从 descr 字段提取内容并清理 <em> 高亮标签
  - 添加 Cookie 预热：先访问日期页面以获取有效 Cookie
  - 移除关键词过滤功能

- **v4.1.0** - 代码结构优化
  - 提取通用工具模块到 `scripts/utils/`
  - 日志配置统一使用 `log_utils.setup_logging()`
  - 网络请求统一使用 `net_utils` (随机延迟、重试)
  - 日期解析统一使用 `date_utils.parse_and_validate_date_range()`
  - 去重存储统一使用 `deduplication.DeduplicationStore`
  - 减少约 80 行重复代码，提高可维护性

- **v4.0.0** - 仅输出 JSON 格式
  - 移除 Excel 输出功能
  - 移除 pandas 和 openpyxl 依赖
  - 移除智能摘要生成功能
  - 移除 output_format 参数
  - 简化为仅输出 JSON 格式

- **v3.0.0** - 仅支持 CLI 版本
  - 移除所有编程接口（main 函数、create_skill、crawl_cls_telegram 等）
  - 移除 Codex Skill 调用支持
  - 简化为纯 CLI 工具

- **v2.1.0** - JSON 输出精简
  - 移除 JSON 输出中的冗余字段：day, hour, time, matched_keywords
  - 保留核心字段：id, content, date

- **v2.0.0** - 优化版本
  - 参考 skill-forge 规范代码结构
  - 参考 cnstock 添加反爬措施
  - 使用 dataclass 配置类
  - User-Agent 轮换
  - 随机延迟机制
  - Cookie 预热
  - 完整类型注解
  - 更好的错误处理
  - CSO 优化的描述
  - 添加合理化表格和红旗警告

- **v1.0.0** - 初始版本
  - 支持日期范围爬取
  - 关键词过滤功能
  - 智能摘要生成
  - Excel 多 Sheet 输出
