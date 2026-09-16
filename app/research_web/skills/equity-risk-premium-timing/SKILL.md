---
name: equity-risk-premium-timing
description: 以显式市盈率和债券收益率口径计算权益风险溢价及滚动经验分位研究信号。
---
# 权益风险溢价择时研究

运行 `scripts/calculate.py <relative-input.json>`。本能力对单条最多 5,000 行日频序列计算 `1 / PE_TTM - 债券收益率百分数 / 100`，再在给定窗口中用“小于等于当前值的样本数 / 窗口样本数”计算经验分位。严格高于上阈值为 `elevated_risk_premium`，严格低于下阈值为 `compressed_risk_premium`，其余为中部信号。

PE 必须为正；输入必须提供指数估值与 10Y 政府债收益率两条序列的 `role`、identity、version、tenor。角色固定为权益指数估值与政府债收益率，version 分别固定为 `pe_ttm_v1` 与 `yield_pct_v1`，期限分别固定为 `spot` 与 `10Y`；identity 必须是非空、受限字符的业务标识。synthetic provider 精确绑定提交 fixture；`user_input` 可提供真实业务 identity 并在输出中原样回传，但不能交换角色、重复身份或改变版本/期限。Wind/DataHub 仅接受 field mapping 明确列出的生产身份；当前白名单为空，因而失败关闭。指数口径、PE 定义版本或债券期限（包括 2Y/10Y 错配）、交易日和复权口径必须等价，provider 与 dataset refs 必须一致。少于窗口的历史返回 `insufficient_history`；未知字段、未来数据、非有限数值和身份、版本、单位或期限不等价均以 `data_not_equivalent` 失败关闭。

输出是研究信号，不是交易或下单指令，并显式给出样本、条件、反例、失效条件与截止日。负盈利指数、PE 定义变化、债券期限变化和结构性估值制度切换会使结论失效。参考工作簿只读核验且未执行公式；DataHub 尚无经核验的联合字段映射，故 `callable=false`、初始 disabled，只有真实 macOS Wind/Excel 外部宿主登记器签发的 v2 HMAC receipt 可启用。
