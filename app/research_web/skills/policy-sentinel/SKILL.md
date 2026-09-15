---
name: policy-sentinel
description: 按关键词与日期筛选政策证据，输出可审计时间线、命中规则和来源已给出的潜在影响对象；不生成投资建议。
---
# 政策哨兵

只处理会话内已取得的政策记录。运行 `scripts/calculate.py <relative-input.json>`，逐条保留 evidence ID、来源引用、日期和命中关键词。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、文档单位、发布日期口径和不适用复权标记均须明确；未来记录或未来数据集引用一律拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。

- 缺少来源引用或证据 ID 时失败关闭。
- 潜在影响对象必须来自输入，不从标题猜测。
- 不把关键词命中解释为真实影响，不给出买卖或配置建议。
- 输出仅供研究。
