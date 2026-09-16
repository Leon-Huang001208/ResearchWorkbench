---
name: fund-penetration
description: 对已提供的基金层级持仓做有界穿透，统一权重单位、检测循环并聚合重复暴露。
---
# 基金持仓穿透

运行 `scripts/calculate.py <relative-input.json>`。逐层相乘父子权重，将 percent/decimal 显式转换为 decimal，重复边和重复叶子路径确定性聚合；所有受理边必须属于同一个完整持仓快照，混合日期返回 `data_not_equivalent`，只在该快照内合并重复边。任一输入子图检测到循环、矛盾类型或权重和超过 100% 时失败关闭。

样本最多 5,000 条披露边，最大层级 20；每个 owner 的 1,000 行上限按聚合前的原始受理行计数。循环以全图拓扑检查失败关闭；合法 DAG 按深度动态聚合到达权重、路径数和日期，再展开下一层，因此汇合路径不会指数重复遍历，同时保持重复叶子路径计数。截止日、持仓披露日、provider、mapping/version、权重单位与不适用复权均严格验证。当前 DataHub 持仓缺少完整覆盖、披露日期和层级身份等价保证，映射为 `callable=false`；仅接受 synthetic/user_input，且 data contract provider 必须与全部 dataset refs 一致。未披露下一层的基金保留为 terminal fund exposure，达到最大层级时结果 partial 并披露限制。安全相对 JSON loader、有限数算术、64 KiB 完整输出与无换行 stdout 复用 `cpu_bounded_v1`。

解释条件：结果只代表输入披露层级和单一快照时点。反例是同一底层证券经两只子基金重复持有，必须聚合而不能按行展示为独立风险；另一反例是把不同披露日边拼成完整树。失效条件包括披露滞后、循环或冲突关系、权重口径不明、层级超过上限和未披露持仓。输出是 research signal，不是交易建议；普通 JSON 不能签发 comparison receipt，真实宿主登记器证据缺失时保持 disabled。
