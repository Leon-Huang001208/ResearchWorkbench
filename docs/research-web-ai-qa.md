# AI 问答

Research Web 的 AI 问答使用迁入的 AlphaDesk React 问答组件及 Node 研究编排。源码来自 AlphaDesk 提交 `1c946b9a0930d3070da7263ffcffe5e8831077c3`，用户确认授权公开提交。前端与执行器各自记录来源和修改，RWB 输入区承接附件、范围、文件格式和幂等提交。

## 执行与资料

- `#/qa` 使用既有 `/api/research/sessions`。快速、深度、Agent 会话的摘要包含 `execution_engine=alphadesk`，SSE 快照附带按序 `qa_events`。
- Host 将回合记录保存在账号会话的私有控制目录。网络断开可以重读状态，进程重启发现未终结的回合显示中断，回合不会自动重放。
- Node 仅通过私有标准输入输出调用 Host。模型、凭据、DataHub、冻结资料、报告格式和交付归 Host 管理。报告计划通过既有报告 SDK，缺乏来源与独立质量证据的输出不能作为已通过报告。
- 当前适配支持文本、Markdown、CSV 和 JSON 附件。PDF、Office 和图片附件，以及 PNG、PPTX 报告的支持是切换前待办。

## 切换状态

`RWB_ALPHADESK_QA=1` 可用于隔离 Host 验证。启用后旧普通 FinGPT 会话从列表与搜索隐藏，旧会话 API 返回 410，专业协作由 `#/specialist` 使用原 DSH 链。私网候选由网关 `alphadesk_qa` 配置传入账号运行环境。

正式常驻切换需固定当前前版及已审候选，验证主实例和网关绑定、活动任务、可恢复的全账号备份与两入口的回滚。真实模型和数据源合计预算上限为人民币 50 元。隔离验收可由 `RWB_QA_ACCEPTANCE_ROOT` 指定共享私有账本，每次 DeepSeek Flash 请求预留峰值缓存未命中输入费用及输出上限，未知价格拒绝调用。此模式关闭未核价供应商的在线 DataHub 请求，冻结资料仍可验收。账本和调用回执须一起留存。DataHub 冻结资料到可验证报告、发现跟踪通知及 Mac Docker 产品验收仍需证据。

[前端迁移说明](../app/research_web/qa_frontend/README.md) · [执行器协议](../app/research_web/qa_worker/README.md) · [受管发布合同](research-web-gateway-upgrade.md)
