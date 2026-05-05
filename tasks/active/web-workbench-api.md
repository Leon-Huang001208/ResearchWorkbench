# Web Workbench — REST API 端点 + 前端集成

## 状态: COMPLETED ✅
## 开始时间: 2026-05-05 20:27 GMT+8
## 完成时间: 2026-05-05 20:42 GMT+8
## 负责人: 龙太子

## 任务清单

| # | 任务 | 状态 |
|---|------|------|
| 1 | 创建 `app/api/models.py` — Pydantic 请求/响应模型 | ✅ |
| 2 | 创建 `app/api/routes/assets.py` — 资产分析路由 | ✅ |
| 3 | 创建 `app/api/routes/scenarios.py` — 情景分析路由 | ✅ |
| 4 | 创建 `app/api/routes/review.py` — 审核路由 | ✅ |
| 5 | 创建 `app/api/routes/signals.py` — 信号路由 | ✅ |
| 6 | 创建 `app/api/routes/ingest.py` — 摄入路由 | ✅ |
| 7 | 更新 `app/api/main.py` — 注册路由 + CORS | ✅ |
| 8 | 创建 `tests/unit/test_api.py` — API 测试 (20/20 通过) | ✅ |
| 9 | 全量测试通过（已有 13 个预存失败，非本次引入） | ✅ |

## 新增文件
- `app/api/models.py` — 11 个 Pydantic 请求/响应模型 + ErrorResponse
- `app/api/routes/__init__.py`
- `app/api/routes/assets.py` — POST /api/assets/analyze, GET /api/assets/{canonical_id}
- `app/api/routes/scenarios.py` — POST /api/scenarios/generate, GET /api/scenarios/{set_id}
- `app/api/routes/review.py` — GET /api/review/pending, POST approve/reject, GET stats
- `app/api/routes/signals.py` — POST create, GET list, POST validate, POST promote
- `app/api/routes/ingest.py` — POST /api/ingest/text, POST /api/ingest/file
- `data_layer/repositories/memory_asset_snapshot_repo.py` — 内存版快照仓储（无 DB 依赖）
- `tests/unit/test_api.py` — 20 个测试用例

## 修改文件
- `app/api/main.py` — 注册 5 个路由模块 + CORS middleware + 更新首页 API 列表

## 测试结果
- `tests/unit/test_api.py`: **20 passed**
- 全量 `pytest -q`: 117 passed, 13 failed (预存，与本次无关)

## 备注
- 需要安装 `python-multipart`（已在环境中安装），供文件上传端点使用
- `ReviewService` 自动连接 DB 的 bug (`next(get_db())` TypeError) 是预存问题
