---
name: fund-evaluation
description: 基于可得基金净值、基准、持仓和费率资料进行基金评价与底稿交付。Use when 用户要求基金分析、基金比较或基金经理评价。
---

# 基金评价

1. 核实基金代码、份额类别、币种、净值类型、期间和对比基准。缺少复权/分红数据时不得把未复权净值收益当总回报。
2. 读取用户上传数据或明确可用的公开来源；检查日期排序、重复、缺失与异常，不补造净值。
   父 Agent 只在当前 Runtime 已暴露 `datahub_get_fund_data` 时直接准备资料；Runtime 只暴露启动时已有可调用来源的 `datahub_*` 工具，已配置且可用的公开、账户或付费来源自动执行，不逐次确认。工具未暴露时不调用、不重试。先读取返回的 `manifest_json` 及 `inputs/datasets/<dataset_id>/manifest.json`，核对 `dataset_id`、`manifest_sha256`、status、请求/实际期间、行数、分页完成、missing 和 limitations，再分配两个原生子 Agent 分别做净值计算与资料风险分析；二者复用父 Agent 已取得的同一 CSV/JSON，不重复取数，approval=never。
   明确期间的净值使用 dataset=nav 与成对 start_date/end_date；无日期的 limit 仅表示最近快照，不能凭 20 条宣称三年表现。基本资料、分红、持仓分别使用 dataset=profile/distributions/holdings（持仓可选 year）；这些调用在工具可用时自动执行。取消后停止；工具不可用时不调用、不重试，也不用脚本联网。
3. 能计算的才计算：区间收益、回撤、波动、相对基准。注明频率、年化假设、样本数；基准/无风险利率不足则省略依赖指标。
   首末观测区间净值变动不自动等于完整日历年度收益：未取得期初前一估值日及分红复权口径时，不称年度收益/总回报。累计净值不等于总回报；业绩比较基准文本不是基准序列；fund_profile当前资料不是历史时点，持仓报告期不是披露日期。缺少基准序列、合同/报告下载能力要明确未取得。
4. 评价规模、持仓集中度、风格稳定性、费率和风险；持仓滞后和披露截止时间必须说明。
5. 使用 resources/research_helpers.py 的 write_deliverables，必须生成 DOCX、HTML、XLSX分析底稿；图表单独写 outputs。确认Office文件可重开。
   XLSX必须另含本次数据集全部原始解析记录（从rows.json/CSV读取）、可复核公式或计算说明、`dataset_id`/`manifest_sha256`及数据日期；不能只有结论指标。CSV对公式文本转义、JSON保留原值，写入Excel的外部文本同样作为文本防止公式注入。DOCX/HTML引用相同 `dataset_id`、`manifest_sha256` 及期间；inputs/datasets是只读材料，不充当报告产物。
6. 缺少数据仍可交付“受限评价”，单列未完成指标和原因，不能以模型猜测替代。

模板见 templates/report.md；计算与生成示例见 scripts/workflow.py。仅做研究分析，不执行交易或承诺收益。
