---
name: company-research
description: 基于已获取材料开展公司业务、财务、竞争力与风险研究并交付报告。Use when 用户要求公司研究、财报点评或公司对比。
---

# 公司研究

1. 确认公司/证券身份、研究期间、问题和现有资料，避免同名实体混淆。
2. 区分上传材料与受控检索获得的来源；每个数值保留口径、币种、期间和来源。没有可用数据就列缺失，不生成假实时数据。
3. 复杂任务使用 DSH 原生 subagent 至少分业务竞争、财务风险两方向；各自仅写唯一前缀文件，主代理整合。不能虚构子任务已执行。
   需审批的af_public_data由父Agent先经用户批准准备资料，读取manifest_json及inputs/datasets的manifest.json核对dataset_id、hash、status、实际期间、行数、missing和limitations，再分配两个子Agent读取同一CSV/JSON；原生委派approval=never，不重复取数、不重试被拒请求。仅使用已经取得的口径计算。
4. 提供结论、业务、财务、对比、风险、待核查问题。估值仅在输入与假设充分时计算，列明假设；不做自动交易。
5. 使用 resources/research_helpers.py 的 write_deliverables 生成用户要求的 DOCX、HTML、XLSX底稿及Markdown；输出路径为 outputs。必须实际重开Office文件验证。
   使用数据集时，XLSX包含原始解析记录、公式或计算说明及dataset_id/manifest_sha256；DOCX/HTML引用相同ID、hash和日期。inputs/datasets只读材料不算报告交付。CSV公式文本已转义，JSON保留原值，写Excel仍须防外部文本公式注入；不足数据在所有文件一致注明。

模板：templates/report.md。脚本调用示例见 scripts/workflow.py（会话 resources 下可用同名公共辅助脚本）。
