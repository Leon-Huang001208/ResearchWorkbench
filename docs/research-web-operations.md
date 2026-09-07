# Research Web 运行与用量

`app/research_web/operations.py` 提供只读聚合，前端位于 `app/research_web/ui/operations.mjs`。它不维护第二套监控数据库，不读取问题正文、附件内容、凭据或上游原始异常。

## 数据来源

- 模型与回合：DSH `session.list`、历史事件和 `projection.py` 中的原生 usage。没有 usage 的历史记录为未知，不记作零。
- Agent 与工具：真实 Claw 会话、`subagent.list/history`、工具开始/结束事件，以及产品审批/取消审计。
- DataHub：查询审计、私有 manifest 和公开快照文件；失败只暴露安全化错误码。
- 服务：只有 `rwb web` 状态文件、命令指纹、项目/数据根与实际 PID 命令签名同时匹配时才显示“进程存在”；实时 `/host.describe` 健康检查单独显示。
- 存储：只遍历 `~/.research-workbench/research-web` 和项目私有 `dsh-source` 的允许分类，不扫描用户磁盘其他位置。
- 报告 Workflow：从版本化运行记录聚合状态、Excel 刷新次数、共享快照、真实子 Agent、实际产物数量和字节数。旧历史产物不计入新运行，损坏 manifest 只返回安全化缺失状态。

## API 与读取策略

`/api/research/operations/usage|tools|datahub|services|storage` 支持分别读取；`/summary` 生成同一页面快照，并在 usage 与 tools 之间复用一次 DSH 会话历史投影。Web 页面使用 `/summary`，避免多个并发历史聚合相互争用 DSH RPC。

时间范围支持今天、7 天、30 天和显式自定义日期。费用只在后端配置模型单价时计算；当前未配置，因此返回 `not_configured`。聚合失败显示明确错误，不回退假数据。

## 边界

页面仅观察，不提供强制停止、服务重启、清库或删除。历史中旧工具名按原生事件原样展示，避免改写审计记录；新任务只使用当前品牌无关工具名。服务状态不把最近成功通信等同于当前健康检查，也不把端口占用等同于受管进程。
