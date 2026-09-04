---
name: fund-evaluation
description: 基于可得基金净值、基准、持仓和费率资料进行基金评价与底稿交付。Use when 用户要求基金分析、基金比较或基金经理评价。
---

# 基金评价

1. 核实基金代码、份额类别、币种、净值类型、期间和对比基准。缺少复权/分红数据时不得把未复权净值收益当总回报。
2. 读取用户上传数据或明确可用的公开来源；检查日期排序、重复、缺失与异常，不补造净值。
   datahub_get_fund_data 由父 Agent 经人工审批准备资料，先读取返回的 manifest_json 及 inputs/datasets 下 manifest.json，核对 dataset_id、hash、status、请求/实际期间、行数、分页完成、missing 和 limitations，再分配两个原生子 Agent 分别做净值计算与资料风险分析；二者读取同一 CSV/JSON，不重复取数，approval=never。
   明确期间的净值使用 dataset=nav 与成对 start_date/end_date；无日期的 limit 仅表示最近快照，不能凭 20 条宣称三年表现。基本资料、分红、持仓分别使用 dataset=profile/distributions/holdings（持仓可选 year），每次调用单独审批；取消/拒绝后停止，不用脚本联网。
3. 能计算的才计算：区间收益、回撤、波动、相对基准。注明频率、年化假设、样本数；基准/无风险利率不足则省略依赖指标。
   首末观测区间净值变动不自动等于完整日历年度收益：未取得期初前一估值日及分红复权口径时，不称年度收益/总回报。累计净值不等于总回报；业绩比较基准文本不是基准序列；fund_profile当前资料不是历史时点，持仓报告期不是披露日期。缺少基准序列、合同/报告下载能力要明确未取得。
4. 评价规模、持仓集中度、风格稳定性、费率和风险；持仓滞后和披露截止时间必须说明。
5. 使用 resources/research_helpers.py 的 write_deliverables，必须生成 DOCX、HTML、XLSX分析底稿；图表单独写 outputs。确认Office文件可重开。
   XLSX必须另含本次数据集全部原始解析记录（从rows.json/CSV读取）、可复核公式或计算说明、dataset_id/manifest_sha256及数据日期；不能只有结论指标。CSV对公式文本转义、JSON保留原值，写入Excel的外部文本同样作为文本防止公式注入。DOCX/HTML引用相同dataset_id、hash及期间；inputs/datasets是只读材料，不充当报告产物。
6. 缺少数据仍可交付“受限评价”，单列未完成指标和原因，不能以模型猜测替代。

模板见 templates/report.md；计算与生成示例见 scripts/workflow.py。仅做研究分析，不执行交易或承诺收益。
