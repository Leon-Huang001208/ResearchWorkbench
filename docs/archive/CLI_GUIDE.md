# CLI 使用指南

本指南详细介绍 AlphaFoundry 的命令行工具使用方法。

## 目录

- [安装命令](#安装命令)
- [analyze 命令](#analyze-命令)
- [scenario 命令](#scenario-命令)
- [ingest 命令](#ingest-命令)
- [review 命令](#review-命令)

## 安装命令

安装项目后，`af` 命令会自动添加到您的 PATH 中。

```bash
# 验证安装
af --help
```

## analyze 命令

生成资产分析快照。

### 基本用法

```bash
af analyze --asset <资产代码>
```

### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--asset` | ✅ | 资产代码，例如：600000.SH, 000001.SZ |
| `--output`, `-o` | ❌ | 输出文件路径，支持 .md 和 .docx |
| `--as-of` | ❌ | 指定快照时间，ISO 格式，例如：2026-05-03 |
| `--use-mock` / `--no-mock` | ❌ | 是否使用模拟数据，默认 `--use-mock` |

### 使用示例

#### 1. 基本分析

```bash
af analyze --asset 600000.SH
```

输出：
```
Analyzing asset: 600000.SH
Snapshot generated successfully for 600000.SH
  As of: 2026-05-03T12:00:00
  PE TTM: 24.9
  Close Price: 58.5
```

#### 2. 输出 Markdown 报告

```bash
af analyze --asset 600000.SH --output report.md
```

#### 3. 输出 Word 文档

```bash
af analyze --asset 600000.SH --output report.docx
```

#### 4. 指定快照时间

```bash
af analyze --asset 600000.SH --as-of 2026-05-03T12:00:00
```

#### 5. 不使用模拟数据

```bash
af analyze --asset 600000.SH --no-mock
```

注意：这需要配置真实的数据源适配器。

## scenario 命令

生成多情景分析报告。

### 基本用法

```bash
af scenario --topic <研究主题>
```

### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--topic`, `-t` | ✅ | 研究主题，例如："人工智能产业发展" |
| `--output`, `-o` | ❌ | 输出文件路径，支持 .md |
| `--subject`, `-s` | ❌ | 主题 ID，可多次指定 |

### 使用示例

#### 1. 基本情景分析

```bash
af scenario --topic "人工智能产业发展对股票市场的影响"
```

#### 2. 输出到文件

```bash
af scenario --topic "美联储政策走向" --output scenario.md
```

#### 3. 指定相关资产

```bash
af scenario --topic "新能源汽车政策" --subject 600000.SH --subject 000001.SZ
```

## ingest 命令

摄入文档并提取断言和事件。

### 基本用法

```bash
af ingest --file <文件路径>
```

### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--file`, `-f` | ✅ | 输入文件路径，支持 .pdf, .txt, .md |
| `--source-type`, `-t` | ❌ | 来源类型：report, news, filing, note |
| `--source-name`, `-s` | ❌ | 来源名称，例如："券商研报" |
| `--title` | ❌ | 文档标题 |

### 使用示例

#### 1. 摄入 PDF 文档

```bash
af ingest --file report.pdf --source-type report --source-name "券商研报"
```

#### 2. 摄入文本文件

```bash
af ingest --file news.txt --source-type news --title "重要新闻"
```

## review 命令

管理审核队列。

### review list

列出待审核的项目。

```bash
af review list
```

#### 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `--limit`, `-n` | ❌ | 显示数量，默认 20 |

### review approve

批准一个断言或事件。

```bash
af review approve <assertion_id>
```

#### 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `assertion_id` | ✅ | 断言 ID |
| `--reviewer`, `-r` | ❌ | 审核人名称，默认 "cli" |

### review reject

拒绝一个断言或事件。

```bash
af review reject <assertion_id>
```

#### 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `assertion_id` | ✅ | 断言 ID |
| `--reviewer`, `-r` | ❌ | 审核人名称，默认 "cli" |

### review stats

显示审核统计信息。

```bash
af review stats
```

### 使用示例

#### 1. 列出待审核项目

```bash
af review list
```

输出：
```
Pending review items:
------------------------------------------------------------
[1] ID: assertion_1234
    Subject: 贵州茅台
    Predicate: 净利润增长
    Confidence: 0.85
    Source: doc_1234
```

#### 2. 批准一个断言

```bash
af review approve assertion_1234 --reviewer "研究员A"
```

#### 3. 拒绝一个断言

```bash
af review reject assertion_1234 --reviewer "研究员A"
```

#### 4. 查看统计

```bash
af review stats
```

输出：
```
Review statistics:
------------------------------------------------------------
Pending assertions: 5
Approved assertions: 12
Rejected assertions: 3
```

## 全局选项

| 选项 | 说明 |
|------|------|
| `--log-level` | 设置日志级别：DEBUG, INFO, WARNING, ERROR |
| `--log-file` | 设置日志文件路径 |

### 示例

```bash
af --log-level DEBUG analyze --asset 600000.SH
af --log-file app.log analyze --asset 600000.SH
```

## 退出代码

| 代码 | 说明 |
|------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 参数错误 |

## 常见问题

### Q: 如何获取更多调试信息？

```bash
af --log-level DEBUG analyze --asset 600000.SH
```

### Q: 生成的报告在哪里？

默认在当前目录，您也可以指定完整路径：

```bash
af analyze --asset 600000.SH --output ./output/report.md
```

### Q: 支持哪些资产代码格式？

目前支持：
- 600000.SH (上海证券交易所)
- 000001.SZ (深圳证券交易所)
- 其他代码格式将在未来版本支持
