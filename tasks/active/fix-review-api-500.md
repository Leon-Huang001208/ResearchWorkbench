# 修复审核 API 500 错误

## 状态: completed

## 问题描述
`GET /api/review/stats` 返回 500 Internal Server Error

## 根因
1. SQLite `canonical_event` 表缺少 `reviewer_status`、`reviewer`、`reviewed_at` 列（旧 schema 未 migration）
2. ORM 模型 (models.py) 定义了这些列，但 `Base.metadata.create_all()` 只创建不存在的表，不会给已有表加列
3. `ReviewService.get_statistics()` 调用 `event_repo.get_pending_review()` 查询 `reviewer_status` 列时触发 `OperationalError`
4. 异常未被捕获，直接导致 500

## 修复内容

### 1. `data_layer/repositories/base.py` — 新增 `ensure_schema()` 函数
- 调用 `Base.metadata.create_all()` 创建缺失的表
- 对 SQLite，检查已有表是否缺少列，自动 `ALTER TABLE ADD COLUMN` 补列
- 已成功为 `canonical_event` 表补上 `reviewer_status`, `reviewer`, `reviewed_at` 三列

### 2. `core/services/review_service.py` — 添加异常保护
- `get_statistics()`: 对 `_assertion_repo.get_pending_review()` 和 `_event_repo.get_pending_review()` 包裹 try/except
- `list_pending_assertions()`: 对 repo 调用包裹 try/except
- `list_pending_events()`: 对 repo 调用包裹 try/except
- DB 错误时记录日志并返回空结果/零统计，不再导致 500

### 3. `app/api/routes/review.py` — 安全初始化
- `get_review_service()` 在创建 ReviewService 前先调用 `ensure_schema()`
- `ensure_schema()` 失败时仅记录警告，不阻塞服务

## 验证结果
- ✅ `python -m pytest tests/unit/test_review_service.py -v` — 21 passed
- ✅ `python -m pytest tests/unit/test_api.py -v` — 20 passed
- ✅ `python -m pytest -q` — 181 passed
- ✅ `GET /api/review/stats` → 200 OK, `{"pending_assertions":0,"approved_assertions":0,"rejected_assertions":0,"pending_events":0}`
- ✅ `GET /api/review/pending` → 200 OK, `[]`
