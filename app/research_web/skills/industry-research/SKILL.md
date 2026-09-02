---
name: industry-research
description: 分析产业链、供需、竞争格局与关键指标并生成可下载研究文件。Use when 用户要求行业研究、主题研究或产业链分析。
---

# 行业研究

1. 明确产业边界、地域、时间和供需口径，先说明哪些数据真实可用。
2. 使用原生 subagent 分工供需与竞争格局；给任务截止要求，不额外建立 Agent 编排系统。
   af_public_data 必须先由父 Agent 经人工审批取数，再把结果交给子 Agent；原生委派的 approval=never，不重试被拒的请求。
3. 关键指标附日期、单位和来源链接；推断与事实分开表述，不虚构规模、增速或公司排名。
4. Python 计算只在 af_run_script 内执行，图表写 outputs；标签注明实际来源和数据截止日。
5. 按 templates/report.md 整合报告，使用 resources/research_helpers.py 生成可打开的 DOCX/HTML/XLSX底稿。
6. 返回实际文件名、主要结论、数据缺口与下一步验证问题；文件未生成时明确未完成原因。
