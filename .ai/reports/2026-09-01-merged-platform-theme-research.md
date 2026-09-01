# Merged Platform Task 5 — Theme Research Packs

## 实施范围

- 新增四个声明式 Research Pack：gold、aerospace、photovoltaic、ai_infrastructure。
- 扩展主题契约：dataset schema/mapping、六类读模型、工作区预填、摄入报告与断点。
- 新增 Registry、Repository、Service 和 `/api/themes` 路由，并在 FastAPI 主应用最小接入。
- 实现 Manifest 生命周期、静态/运行时插件能力门、统一 ThemeObservation、dry-run/显式 apply、source hash、row identity 幂等、accepted/quarantined/rejected/duplicate 和断点恢复。
- 明确拒绝 LSH `score_hint` catalysts、`driver-summary`、策略、订单及评分字段；创业板 50 仅作为光伏/AI 的 index market proxy。

## TDD 证据

首次 RED：

```text
python -m pytest tests/unit/test_theme_pack_registry.py tests/unit/test_theme_research_service.py tests/unit/test_theme_research_api.py -q
结果：3 个 collection error，分别缺少 Registry、Repository 与 API route（符合新能力尚未实现的预期）。
```

随后为同文件重复、可选 CSV 字段、JSON-like 插件输入、分组数字/日期、断点 source hash、拒绝统计持久化和幂等 manifest sync 分别增加失败测试并观察预期失败，再实现最小修复。

## 已执行验证

```text
python -m pytest tests/unit/test_theme_pack_registry.py tests/unit/test_theme_research_service.py tests/unit/test_theme_research_api.py -q
阶段结果：23 passed（增加后续边界测试前的中间 GREEN）。
```

真实 LSH dry-run 使用新增 CLI 与内存 SQLite；未连接或写入目标数据库：

```text
python scripts/migrate_lsh_theme_data.py \
  --source /Users/leon/Desktop/LSH_Project/manual_data/skills \
  --dry-run \
  --output /tmp/lsh-theme-migration-report.json

source: /Users/leon/Desktop/LSH_Project/manual_data/skills
files scanned: 28
accepted: 6165
quarantined: 0
rejected: 16
duplicate: 974
applied: 0
source hashes: 28
checkpoints: 28
```

16 条 rejected 包括两份含 `score_hint` 的 catalysts（4+4）、`driver-summary`（1）、两条数值缺单位的 macro rows（2），以及未映射的非 official optical-module customs 文件（5）。974 条 duplicate 来自同一官方海关文件内相同 source hash + canonical row identity 的重复记录；未重复写入。每个文件均生成 SHA-256 source hash 与 checkpoint。

最终验证：

```text
python -m pytest \
  tests/unit/test_theme_pack_registry.py \
  tests/unit/test_theme_research_service.py \
  tests/unit/test_theme_research_api.py \
  tests/unit/test_lsh_theme_migration.py \
  tests/unit/test_merged_platform_contracts.py \
  tests/unit/test_merged_platform_migration.py -q
结果：106 passed

python -m ruff check <10 个 Task 5 Python 文件>
结果：All checks passed

python -m black --check <10 个 Task 5 Python 文件>
结果：10 files would be left unchanged

python -m isort --check-only <10 个 Task 5 Python 文件>
结果：通过
```

## 未验证项

- 未在真实 PostgreSQL + pgvector 实例执行 apply 或查询性能验证；SQLite 单元集成不能替代生产数据库验证。
- 未执行 LSH 数据 apply；真实扫描严格保持 dry-run，无数据库写入。
- LSH 中没有可映射的黄金 CSV；黄金纵切使用契约 fixture 完成 apply、幂等与六类投影验证，生产黄金数据仍需 Connector/迁移源。
- 本任务不修改桌面端，不涉及 Windows 安装包；也未宣称 Windows 验证。
