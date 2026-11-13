# FinGPT

Research Web 的 FinGPT 使用迁入的 AlphaDesk React 问答组件及 Node 研究编排。源码来自 AlphaDesk 提交 `1c946b9a0930d3070da7263ffcffe5e8831077c3`，用户确认授权公开提交。前端与执行器各自记录来源和修改，RWB 输入区承接附件、范围、文件格式和幂等提交。

## 执行与资料

- `#/qa` 使用既有 `/api/research/sessions`。快速、深度、Agent 会话的摘要包含 `execution_engine=alphadesk`，SSE 快照附带按序 `qa_events`。
- Host 将回合记录保存在账号会话的私有控制目录。网络断开可以重读状态，进程重启发现未终结的回合显示中断，回合不会自动重放。
- Node 仅通过私有标准输入输出调用 Host。模型、凭据、DataHub、冻结资料、报告格式和交付归 Host 管理。报告计划通过既有报告 SDK，缺乏来源与独立质量证据的输出不能作为已通过报告。
- 支持文本、Markdown、CSV、JSON、PDF、Word（`.docx`）、Excel（`.xlsx`）和 PowerPoint（`.pptx`）附件。PDF 和 Office 通过原生隔离环境提取有界正文。Excel 使用已保存的单元格值，扫描件、嵌入对象和空正文会提示缺口。
- PNG、JPEG、WebP 和静态 GIF 图片仅由 Host 发给本轮已配置的视觉模型。支持 DeepSeek 官方 `deepseek-flash` 和采用已知 GPT‑4o／GPT‑4.1 模型标识的 OpenAI-compatible 连接。图片解读须另有原始证据支撑，才能用于报告质量判定。[DeepSeek 图片输入文档](https://api-docs.deepseek.com/guides/vision/)
- 可显式选择 PNG 和 PPTX 报告。它们与 HTML、DOCX、PDF 使用相同的冻结正文，经 Host 重建核验并归档后提供下载。

## 切换状态

`RWB_ALPHADESK_QA=1` 可用于隔离 Host 验证。启用后旧普通 FinGPT 会话从列表与搜索隐藏，旧会话 API 返回 410，专业协作由 `#/specialist` 使用原 DSH 链。私网候选由网关 `alphadesk_qa` 配置传入账号运行环境。

正式常驻切换需固定当前前版及已审候选，验证主实例和网关绑定、活动任务、可恢复的全账号备份与两入口的回滚。

`apply-fingpt` 使用现有 Native 发布事务。事务将同一候选的 `alphadesk_qa` 写入主实例安装清单和私网网关配置，启动后核对两端健康。主实例重新启动时根据与当前版本匹配的安装清单读取开关。回滚恢复前版清单和网关配置。正式上线前必须完成真实资料交接、在线自动跟踪和全账号恢复演练。

隔离验收的模型和数据源共用人民币 50 元预算。由操作员用 `RWB_QA_ACCEPTANCE_ROOT` 为主 Host 和私网租户指定同一私有账本目录。每次 DeepSeek Flash 请求在发送前按人民币高峰价预留完整缓存未命中上下文和输出上限。收到身份一致且完整结束的官方流后，记录响应 ID 和缓存命中、未命中及输出 token 数，并按高峰价核减预留，计算结果为费用上界。旧账本预留、缺失或不一致的用量及未完成的流保留全部预留，需供应商账单核对后才能释放。账本和调用回执一起留存。

验收期间，未核价的 DataHub 新查询、发现预览与资料刷新冻结、以及尚未留存正文的公开网页读取在发出外部请求前拒绝。已有 DataHub 查询回执、冻结资料和已留存网页仍按原有权限和完整性校验读取。

[前端迁移说明](../app/research_web/qa_frontend/README.md) · [执行器协议](../app/research_web/qa_worker/README.md) · [受管发布合同](research-web-gateway-upgrade.md)
