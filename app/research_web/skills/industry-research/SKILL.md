---
name: industry-research
description: 分析产业链、供需、竞争格局与关键指标并生成可下载研究文件。Use when 用户要求行业研究、主题研究或产业链分析。
---

# 行业研究

1. 明确产业边界、地域、时间和供需口径，先说明哪些数据真实可用。
2. 使用原生 subagent 分工供需与竞争格局；给任务截止要求，不额外建立 Agent 编排系统。
   需公开资讯时，父 Agent 先使用 datahub_search_news 经人工审批准备资料；产业链与财务能力只有在目录显示来源已适配后才可使用。读取 manifest_json 及 inputs/datasets 的 manifest.json，核对 dataset_id、hash、status、期间、行数、missing 和 limitations，再分配两个子 Agent 读取同一 CSV/JSON；原生委派 approval=never，不重复取数、不重试被拒请求。只基于已获得口径计算。
3. 关键指标附日期、单位和来源链接；推断与事实分开表述，不虚构规模、增速或公司排名。
4. Python 计算只在 research_run_script 内执行，图表写 outputs；标签注明实际来源和数据截止日。
5. 按 templates/report.md 整合报告，使用 resources/research_helpers.py 生成可打开的 DOCX/HTML/XLSX底稿。
   XLSX必须包含数据集原始解析记录、公式或计算说明、dataset_id/manifest_sha256；DOCX/HTML引用同一ID、hash和日期。inputs/datasets只读材料不能充当报告。CSV公式文本已转义、JSON保留原值，写Excel时外部文本不作为公式执行。
6. 返回实际文件名、主要结论、数据缺口与下一步验证问题；文件未生成时明确未完成原因。
