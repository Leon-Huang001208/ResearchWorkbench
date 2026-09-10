# Research Workbench Research Web 当前架构

这是当前研究产品的唯一架构主入口。源码范围为 `app/research_web/`；旧 `app/api`、量化业务和 merged-platform 图文属于历史，不是此入口的依赖。

研究布局、能力中心与架构更新检查已实施。当前 Web 包含研究台按需数据入口、独立资产观察、Claw 具体报告 Workflow、会话快照交接、实际产物及只读“运行与用量”聚合；DataHub 同时迁入天软 CJPY 的四项已实现能力，但缺少本机依赖或授权时仍不可调用。东方财富基金和财联社是当前无需专业配置即可真实调用的来源。Phase 2A 还增加功能开关保护的只读 MCP Registry 市场，聚合官方与私有目录但不安装或运行服务器。逐项变更见 [迭代核对](review-record.md)。图形通过不替代产品、数据覆盖或真实连接审查。

## 阅读顺序

前端外观以 [Research Web 外观与主题](../../research-web-appearance.md) 为准：Codex 风格、Light/Dark 与用户原图符号；不改变下述服务部署和研究契约。

1. [部署与职责](01-system.md)：启动路径、模块边界和存储归属。
2. [研究协议与状态](02-research-runtime.md)：提交、SSE、恢复、审批、停止及页面交接。
3. [数据与文件](03-data-files.md)：研究台、DataHub 静态目录、路由、资料快照、附件、产物和独立交付。
4. [接口清单](04-api.md)：当前路由与请求边界。
5. [安全与验证](05-security-validation.md)：可执行边界、测试层次与未覆盖部署。
6. [文档清单契约](06-documentation-contract.md)：仓库内门禁、更新标记与负向验收。
7. [能力管理](07-capabilities.md)：Skill、Tool、Workflow、数据目录，及包、版本、原生发现和会话只读资源。
8. [运行与用量](../../research-web-operations.md)：真实 usage、Agent、工具、DataHub、服务健康和项目存储聚合。

可交互图文位于仓库 `outputs/research-web-architecture/`，也可从 Web 设置的「架构文档」打开。JSON 图源在本目录 `diagrams/`。十图均以实际源码为依据；本轮新增报告运行序列与 Excel 数据流，并更新模块依赖、运行状态和交付状态。最终图均达到 showcase 9/9、零错误零警告，并通过四视口检查与人工截图核对。图形证据与产品验收分开保存。

## 不在本轮范围

不新增 PostgreSQL 前置条件、Evidence/Claim、第二研究引擎、线上 Skill 商店或桌面适配。Phase 2A 的 MCP 市场仅浏览 Registry 元数据：身份保持 `(registry_id, server_name, version)`，第三方字段在数据层保持有界 Unicode plain text、只在最终 HTML sink 转义一次且不加载远程图标；认证 Registry 与 OAuth 端点要求 HTTPS，无认证 HTTP 仅限精确 loopback。包类型支持与不可变引用是独立目录事实，不承诺可安装。Publisher 只生成外部 CLI 交接材料并明确 `executed:false`。MCP 安装/运行时和通用 Automation/外发分别留待 Phase 2B/2C。研究台市场页是按需查询和快照入口，不是旧市场首页或后台行情管线。

## 启动与验收基线

从仓库根目录使用安装后的项目命令。管理器只启动和停止指纹匹配的项目进程，端口已有其他服务时直接失败：

```bash
rwb web start
rwb web status
rwb web restart
rwb web stop
```

模型仅在产品设置中授权。专属运行时使用 3081，Web 使用 8088；用户原 3080 不被更改。后台状态和日志保存在 `~/.research-workbench/`，终端退出不结束服务。

旧研究目录先用 `rwb migrate-research-data --dry-run` 查看迁移摘要，再执行复制。凭据不会迁移；新实例需在设置页重新填写。Web 恢复验证通过后可使用 `--archive-source` 将旧目录改为只读迁移备份。

当前实施分支为 `codex/web-consolidation`。此前记录见 [原研究验收](../../research-web-acceptance.md)、[DataHub 资料共享验收](../../../.ai/reports/2026-09-02-datahub-acceptance.md)；本轮在这些真实会话和文件基础上新增研究台与监控，并重新执行公开来源、接口、浏览器和全套 Research Web 回归。

## 当前报告 Workflow 验收边界

- 华安 ETF 周报已完成两份 Wind 底稿真实刷新、一次共享快照和两个真实 Claw 子 Agent；DOCX、HTML、XLSX 均已生成并可重开。
- 该次运行仍为 `delivery_incomplete`：模型 Payload 未覆盖全部必需区块。文件有效不等于内容合同完整，因此没有改记 `completed`，也未开放日程。
- 创业板 50 的活动底稿实际为 iFinD/同花顺公式；误标 Wind 的文件只作 `legacy_mislabeled` 历史资源。当前机器未发现 iFinD Excel 插件，真实探测返回 `formula_error`，所以该 Workflow 尚不能完成真实刷新。
- 华安 ETF 投资风向标和 AI 周报尚未满足本轮完整真实运行门槛。分支因此暂不合并、不推送、不清理旧 worktree；这些动作只在必需验收全部通过后执行。
