# A 股深度研究

## 用途

`a-share-deep-research` 是 AlphaFoundry 通用研究中心注册的首个可执行 Research Template，将单一 A 股公司研究约束为可恢复、可追溯的 Research Run。它不是独立页面；宏观、商品、指数和行业使用各自模板。该模板不输出仓位、交易指令或自动下单结果。

## 使用方式

先阅读同目录 [SKILL.md](SKILL.md)，再从研究中心或资产观察的快捷入口创建或恢复 `a_share_deep_research` 任务。对象必须是 `security` ResearchSubject；每项可发布结论必须关联稳定来源，数值需携带单位和期间。五类证据定义见 [references/a-share-evidence-contract.md](references/a-share-evidence-contract.md)。

## 交付物

- 可审计的 Research Run 状态、门禁、不可变产物与当前观点投影。
- 仅在门禁全部通过后生成的决策卡、Markdown 与 Word 报告。
- 数据源降级、证据缺口、冲突及恢复节点的明确记录。
