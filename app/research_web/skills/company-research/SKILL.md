---
name: company-research
description: 基于已获取材料开展公司业务、财务、竞争力与风险研究并交付报告。Use when 用户要求公司研究、财报点评或公司对比。
---

# 公司研究

1. 确认公司/证券身份、研究期间、问题和现有资料，避免同名实体混淆。
2. 区分上传材料与受控检索获得的来源；每个数值保留口径、币种、期间和来源。没有可用数据就列缺失，不生成假实时数据。
3. 复杂任务使用 DSH 原生 subagent 至少分业务竞争、财务风险两方向；各自仅写唯一前缀文件，主代理整合。不能虚构子任务已执行。
4. 提供结论、业务、财务、对比、风险、待核查问题。估值仅在输入与假设充分时计算，列明假设；不做自动交易。
5. 使用 resources/research_helpers.py 的 write_deliverables 生成用户要求的 DOCX、HTML、XLSX底稿及Markdown；输出路径为 outputs。必须实际重开Office文件验证。

模板：templates/report.md。脚本调用示例见 scripts/workflow.py（会话 resources 下可用同名公共辅助脚本）。
