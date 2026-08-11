---
name: a-share-deep-research
description: Use for evidence-first A-share company deep research, including validating whether a valuation narrative is supported by financial statements, industry data, consensus estimates and risk disclosures. Creates or resumes an AlphaFoundry Research Run and returns a traceable decision card and report only after quality gates pass.
---

# A 股深度研究

使用 AlphaFoundry 研究中心注册的 `a_share_deep_research` Research Template，不得把未验证资料直接写成报告结论。本 Skill 是通用 Research Run 的领域能力，不是独立页面；研究事实通过现有 Document、Assertion、EvidencePackage 与 Citation 契约保存。

## 输入门槛

- 确认 `subject_type=security` 的单一 A 股标的、研究时点和明确问题；ETF、指数、宏观、商品或行业对象必须选择其各自模板，不能误用本 Skill。
- 按 `licensed → official → public → user` 收集资料；每次降级记录数据缺口与来源等级。
- 准备五类可追溯证据：`financial`、`industry`、`valuation`、`risk`、`consensus`。每项都有稳定 `source_ref`。
- 数值证据同时提供数值、单位、期间；涉及计算时提供计算式。

详见 [references/a-share-evidence-contract.md](references/a-share-evidence-contract.md)。

## 执行流程

1. 从统一研究中心或资产观察快捷入口选择 `a_share_deep_research`，创建带 `ResearchSubject` 的 Research Run，持久化问题、时点、附件引用和内部规范化证据。
2. 规划来源并标准化证据；不够的数据标为缺口，不能用推测补齐。
3. 形成按五类证据组织的 Research Notes 与 Claim；每个 Claim 绑定引用。
4. 对叙事和财报执行反方检验：关注三表勾稽、应收/存货/现金流、行业约束、估值隐含假设和舞弊红旗。
5. 执行引用、数值、五类覆盖和冲突门禁。任一失败即 `blocked`；补充资料后从验证阶段恢复。
6. 仅在全部门禁通过后发布决策卡和 Markdown/Word 报告。

## 输出规则

- 决策卡只给研究结论、置信度、驱动、催化剂、风险、失效条件、待验证问题和数据覆盖度；不提供仓位或交易指令。
- 观点与报告必须可反向追溯到 `source_ref`；存在未解决冲突时显示阻塞原因而非发布结论。
- 对用户上传材料与公开资料保留来源标记，避免混淆授权数据、官方披露和二手资料。

## 方法论焦点

- 先识别市场价格隐含的叙事，再检验财报与行业现实是否支持。
- 三张表分析必须检查利润、营运资本、现金流和负债/资本开支之间的勾稽关系。
- 对异常应收、存货、减值、关联往来、资本化和非经常性收益提出反方问题；没有证据时维持待验证状态。
- 估值与一致预期属于证据，不是结论；说明其时点、覆盖范围和可能的滞后。
