---
name: factor-database-research
description: 基于用户本机配置的只读数据库快照开展可复现因子研究。Use when 用户要求查询因子库、提取单表数据、分组回测或核对数据库结构。
---

# 因子库研究

1. 先调用 `datahub_get_database_schema`，按数据库、表、列三级确认真实标识；不得猜测库表列名，也不得请求原始 SQL。
2. 只用 `datahub_query_table` 提交显式数据库、表、列、过滤、排序和分页参数。不能用 JOIN、子查询、聚合、表达式、存储过程或写操作绕过 DataHub。
3. 读取工具返回的 `manifest_json` 和 `inputs/datasets/<dataset_id>/manifest.json`，核对 `dataset_id`、`manifest_sha256`、查询参数、行数、状态、字段和 limitations。若出现 `tls_certificate_unverified`，在结论中明确披露。
4. 复杂清洗、分组与统计只对本会话快照调用 `research_run_script`；脚本不得联网或直连数据库。记录数据集哈希、样本筛选、缺失值处理和可复现参数。
5. 数据不足、权限不安全、凭据库不可用或来源未重启物化时停止取数，报告受限原因，不猜测、不更换数据源。

BP 十分位示例见 `examples/bp_decile.md`。
