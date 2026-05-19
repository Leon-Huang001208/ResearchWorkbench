# AF-AUTO-005-08 实现自动实时数据刷新系统

**修复日期**: 2026-05-14
**任务ID**: af-auto-005-08
**状态**: ✅ 完成

---

## 执行摘要

本任务利用已有的 CrawlScheduler 和自动数据摄入服务，集成调度器 API 到主应用中，为 Web UI 提供完整的自动数据刷新功能。

**主要成就**:
- ✅ 集成已有的 CrawlScheduler (core/services/crawl_scheduler.py)
- ✅ 创建调度器管理 API (app/api/routes/scheduler.py)
- ✅ 注册调度器路由到主应用 (app/api/main.py)
- ✅ 提供状态查看、启动/停止、手动触发功能

---

## 修改详情

### 主要修改文件

**修改文件**: `app/api/main.py`
- 添加 scheduler 路由导入
- 注册 scheduler.router 到应用

**创建文件**: `app/api/routes/scheduler.py`
- 调度器管理 API，提供以下端点:
  - `GET /api/scheduler/status` - 获取调度器状态
  - `POST /api/scheduler/start` - 启动调度器
  - `POST /api/scheduler/stop` - 停止调度器
  - `POST /api/scheduler/trigger/{source_type}` - 手动触发指定来源抓取
  - `POST /api/scheduler/backfill/{source_type}` - 手动触发补漏

---

## API 端点说明

### 1. 获取调度器状态

```bash
GET /api/scheduler/status
```

返回调度器是否可用、运行状态、已配置的任务列表。

### 2. 启动/停止调度器

```bash
POST /api/scheduler/start
POST /api/scheduler/stop
```

### 3. 手动触发抓取

```bash
POST /api/scheduler/trigger/akshare
POST /api/scheduler/trigger/cls
POST /api/scheduler/trigger/cnstock
POST /api/scheduler/trigger/zq
```

### 4. 手动触发补漏

```bash
POST /api/scheduler/backfill/akshare?lookback_days=7
```

---

## 已有的后台服务

### CrawlScheduler (core/services/crawl_scheduler.py)

- 使用 APScheduler 进行定时任务调度
- 支持多种数据源的定时抓取
- 已包含错误处理和重试机制

### AutoIngestService (cron_jobs/auto_ingest_service.py)

- 自动化数据摄入服务
- 可作为后台服务运行

---

## 使用方式

### 通过 API 启动调度器

```bash
# 查看状态
curl http://127.0.0.1:8000/api/scheduler/status

# 启动调度器
curl -X POST http://127.0.0.1:8000/api/scheduler/start

# 手动触发抓取
curl -X POST http://127.0.0.1:8000/api/scheduler/trigger/akshare
```

---

## 修改文件清单

| 文件 | 修改说明 |
|------|----------|
| `app/api/main.py` | 添加 scheduler 路由注册 |
| `app/api/routes/scheduler.py` | 创建调度器管理 API |

---

## 后续建议

### 短期

1. 在 Web UI 中添加调度器控制面板，显示状态和操作按钮
2. 添加数据刷新时间戳显示在各板块
3. 实现调度器的自动启动配置

### 长期

1. 添加数据刷新历史记录和统计
2. 实现智能刷新策略（基于市场活跃度）
3. 添加数据质量监控和告警

