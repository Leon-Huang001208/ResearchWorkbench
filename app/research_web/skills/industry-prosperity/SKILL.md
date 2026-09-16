---
name: industry-prosperity
description: 对已提供的行业预聚合指标按方向和权重计算透明的景气变化分数。
---
# 行业景气度

运行 `scripts/calculate.py <relative-input.json>`。每项贡献固定为 `(current-prior)/abs(prior)×100×direction×weight`，行业分数为贡献和除以权重和；不扫描全市场，不推断指标方向或权重。

样本最多 50 个行业、每行业 1,000 项且总计不超过 5,000 项；report period end、截止日、provider、mapping/version、原生指标单位一致性、百分比变化和不适用复权严格验证。当前 DataHub 预聚合表未建立已核验映射，标记 `callable=false`，只接受 synthetic/user_input 且 provider 与 dataset refs 必须一致。prior 为 0、报告期错位或行业指标数不足时失败或明确 partial。完整计算后，嵌套 `indicator_contributions` 在所有行业间全局最多投影 128 条，并用 row delivery 披露省略数；合法 5,000 项近上限输入仍必须成功且完整 envelope 不超过 64 KiB。

解释条件：同一指标的 current/prior 必须可比。反例是库存下降在去库存完成时可能为正向、在需求崩塌时也可能为负向，因此 direction 必须由研究者给出并接受反证。失效条件包括指标定义变化、季节性未处理、报告期不同、权重失真和结构性断点。improving/weakening 仅为 research signal，不是交易建议；普通 JSON 无法自签对照，可信宿主 receipt 缺失时保持 disabled。
