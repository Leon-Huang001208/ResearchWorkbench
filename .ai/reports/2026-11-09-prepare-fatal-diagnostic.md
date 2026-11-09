# 修订候选登记保留 Git fatal 历史诊断

Mac mini Web 工程维护。WeKnora 候选的原 prepare 失败回执记录
`command_failed`、退出码 128 及有界 stderr 摘要。经独立的原合并父链验证恢复到
`prepared` 后，修订入口仍因该历史诊断返回 `UNPUBLISHED_STATE_INVALID`。

同形夹具已复现。修复只接受已恢复的原诊断形状并原样保全；信号、spawn 错误、
无 stderr 摘要、其他失败类别及发布状态不确定仍拒绝。所有既有 Git 身份、父链、
远端、可恢复备份及 CI 门仍独立校验。真实产品候选另行办理登记和 CI。

Product-Progress: not-required — 本次仅修复受管 Git 历史诊断读取，不改变产品入口或界面。
