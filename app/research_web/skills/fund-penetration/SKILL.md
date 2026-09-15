---
name: fund-penetration
description: 对已提供的基金层级持仓做有界穿透，统一权重单位、检测循环并聚合重复暴露。
---
# 基金持仓穿透

运行 `scripts/calculate.py <relative-input.json>`。逐层相乘父子权重，将 percent/decimal 显式转换为 decimal，重复边和重复叶子路径确定性聚合；重复披露和完整路径的输出日期取最晚披露日。任一输入子图检测到循环、矛盾类型或权重和超过 100% 时失败关闭。

样本最多 5,000 条披露边，最大层级 20；截止日、持仓披露日、provider、mapping/version、权重单位与不适用复权均严格验证。未披露下一层的基金保留为 terminal fund exposure，达到最大层级时结果 partial 并披露限制。安全相对 JSON loader、有限数算术、64 KiB 完整输出与无换行 stdout 复用 `cpu_bounded_v1`。

解释条件：结果只代表输入披露层级和截止时点。反例是同一底层证券经两只子基金重复持有，必须聚合而不能按行展示为独立风险。失效条件包括披露滞后、循环或冲突关系、权重口径不明、层级超过上限和未披露持仓。输出是 research signal，不是交易建议；未完成真实对照前保持 disabled。
