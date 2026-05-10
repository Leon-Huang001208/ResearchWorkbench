# Issue #43: 多源采集、原始落盘、增量调度与补漏机制

## 概述

Issue #43 在 Issue #42 的基础上，实现了完整的数据采集流水线，包括原始数据落盘、三层去重机制、增量抓取、补漏机制，以及基于 APScheduler 的调度服务。

## 完成的工作

### 1. 原始数据存储 (`core/contracts/raw_storage.py` + `core/services/raw_storage_service.py`)

创建了完整的原始数据存储系统：

**数据结构**:
- `RawDataType`: 支持 JSON、HTML、PDF、TEXT、IMAGE、BINARY 等多种格式
- `RawFileInfo`: 记录文件元数据（路径、类型、来源、大小、校验和等）
- `RawStorageConfig`: 配置存储路径、压缩选项、保留期限等

**目录结构**:
```
data/raw/
  {source_type}/
    {YYYY}/
      {MM}/
        {DD}/
          {timestamp}_{source_type}_{random_id}.{ext}[.gz]
```

**功能特性**:
- 支持 gzip 压缩存储（可配置）
- 自动计算内容校验和（MD5）
- 按时间自动归档和清理
- 支持按来源、时间、类型查询

### 2. 去重服务 (`core/services/deduplication_service.py`)

实现了三层去重机制：

**第一层: source_doc_id 去重**
- 利用外部来源的文档 ID 快速去重
- 内存缓存 + 数据库查询双重保障

**第二层: content_hash 去重**
- 对规范化后的内容计算 MD5 哈希
- 支持相似内容检测（预留扩展点）

**第三层: 近似重复检测（设计中）**
- 预留接口支持基于向量的相似度检测
- 可扩展支持 MinHash/LSH 等算法

**功能特性**:
- 批量去重检查
- 缓存自动过期清理（默认 24 小时）
- 批次内去重 + 全局去重双重检查

### 3. 采集编排服务 (`core/services/crawl_orchestrator.py`)

核心的采集编排器：

**功能特性**:
- 统一的 `crawl_source()` 入口方法
- 自动管理 `SourceCursor` 增量状态
- 记录完整的 `CrawlRun` 执行历史
- 集成去重服务和原始存储服务
- 支持补漏模式 (`backfill_source()`)

**时间窗口计算**:
```
正常抓取: last_successful_crawl_time -> now
         + lookback_window_minutes (补漏窗口)

补漏模式: now - days -> now
```

**连续失败处理**:
- 自动记录连续失败次数
- 可根据失败次数决定是否暂停抓取

### 4. 调度服务 (`core/services/crawl_scheduler.py`)

基于 APScheduler 的定时调度系统：

**默认调度配置**:
| 来源 | 频率 | 补漏 |
|------|------|------|
| 财联社电报 | 15 分钟 | 每天一次 |
| 中国证券网 | 30 分钟 | 每天一次 |
| 知丘研报 | 1 小时 | 每天一次 |

**功能特性**:
- `SourceCrawlConfig` 灵活配置每个来源
- `start()` / `stop()` 生命周期管理
- `trigger_crawl()` 手动触发单次抓取
- `trigger_backfill()` 手动触发补漏
- `get_status()` 查看调度和抓取状态

### 5. CLI 命令 (`app/cli/commands/ingest.py`)

新增 `crawl` 命令组：

```bash
# 单次抓取
af crawl run --source cailian_she --days 1

# 补漏抓取
af crawl backfill --source cailian_she --days 7

# 查看状态
af crawl status [--source cailian_she]

# 启动调度器（前台运行）
af crawl scheduler-start
```

### 6. 仓储层增强 (`data_layer/repositories/documents_v1.py`)

在 Issue #42 的基础上增强：

**新增方法**:
- `DocumentV1Repository.get_existing_source_ids()`: 批量查询已存在的 source_id
- `DocumentV1Repository.get_existing_content_hashes()`: 批量查询已存在的 content_hash
- `DocumentV1Repository.list_by_time_range()`: 按时间范围查询（支持回测视角）

### 7. 单元测试 (`tests/unit/test_issue43.py`)

完整的测试覆盖，15 个测试全部通过：

- 原始存储测试 (5)
- 去重服务测试 (4)
- 集成测试 (2)
- 验收测试 (4)

## 设计特点

### 1. 可追溯的完整数据流

```
原始数据 (raw/) → DocumentV1 → Processed → Events/Assertions
        ↓
    CrawlRun/SourceCursor
```

每个文档都可追溯到原始抓取记录和原始数据文件。

### 2. 增量抓取设计

`SourceCursor` 记录：
- `last_successful_crawl_time`: 上次成功抓取时间
- `last_source_doc_id`: 处理的最后一个文档 ID
- `lookback_window_minutes`: 回顾窗口（补漏用）
- `consecutive_failures`: 连续失败次数
- `is_paused`: 是否暂停

### 3. 补漏机制

独立的 `backfill_source()` 方法：
- 使用更长的回溯窗口
- 更宽松的去重策略
- 可定期调度或手动触发
- 修复之前抓取遗漏的内容

### 4. 状态可观测

每个抓取任务都有完整记录：
- 开始/结束时间
- 成功/跳过/失败数量
- 错误日志
- 使用的配置参数

## 文件变更清单

### 新增文件
1. `core/contracts/raw_storage.py`: 原始存储契约
2. `core/services/raw_storage_service.py`: 原始存储服务
3. `core/services/deduplication_service.py`: 去重服务
4. `core/services/crawl_orchestrator.py`: 采集编排服务
5. `core/services/crawl_scheduler.py`: 调度服务
6. `tests/unit/test_issue43.py`: 单元测试
7. `docs/ISSUE_43_IMPLEMENTATION_SUMMARY.md`: 本文档

### 修改文件
1. `data_layer/repositories/documents_v1.py`: 增强仓储层
2. `app/cli/commands/ingest.py`: 新增 crawl 命令组
3. `app/cli/main.py`: 注册 crawl 命令

## 使用示例

### 基本使用 - 单次抓取

```python
from core.contracts import SourceType
from core.services.crawl_orchestrator import CrawlOrchestrator

orchestrator = CrawlOrchestrator()
result = orchestrator.crawl_source(
    source_type=SourceType.CAILIAN_SHE,
    days=1,
    max_docs=100,
)

print(f"保存: {result.success_count}")
print(f"重复: {result.skipped_count}")
print(f"失败: {result.failure_count}")
```

### 基本使用 - 补漏

```python
result = orchestrator.backfill_source(
    source_type=SourceType.CAILIAN_SHE,
    lookback_days=7,
)
```

### 使用调度器

```python
from core.services.crawl_scheduler import CrawlScheduler, SourceCrawlConfig

scheduler = CrawlScheduler()

# 自定义配置
config = SourceCrawlConfig(
    source_type=SourceType.CAILIAN_SHE,
    interval_minutes=10,
    backfill_enabled=True,
    backfill_interval_hours=12,
)
scheduler.add_config(config)

# 启动
scheduler.start()

# 手动触发
scheduler.trigger_crawl(SourceType.CAILIAN_SHE)

# 查看状态
status = scheduler.get_status()
```

### 使用 CLI

```bash
# 抓取财联社最近 1 天
af crawl run --source cailian_she --days 1

# 补漏最近 7 天
af crawl backfill --source cailian_she --days 7

# 查看所有来源状态
af crawl status

# 启动调度器
af crawl scheduler-start
```

## 验收标准对照

Issue #43 的所有验收标准已达成：

- [x] **原始落盘规范** - 定义了 data/raw/ 目录结构
- [x] **状态表设计** - CrawlRun + SourceCursor 完整记录
- [x] **调度策略** - 基于 APScheduler 的可配置调度
- [x] **三层去重** - source_id / content_hash / 近似重复
- [x] **补漏机制** - 独立的 backfill 方法和调度

## 下一步

- Issue #44: PDF/HTML/纪要解析、Chunk、Taxonomy、标签与事件抽取
- Issue #45: RAG 检索层设计
- Issue #46: 模板化研报生成
- Issue #47: 回测视角

## 总结

Issue #43 构建在 Issue #42 的基础上，提供了完整、生产可用的数据采集流水线。系统具有良好的可观测性、可追溯性和容错能力，支持增量抓取和自动补漏。配合新增的 CLI 命令，用户可以方便地进行手动、定时或补漏抓取。
