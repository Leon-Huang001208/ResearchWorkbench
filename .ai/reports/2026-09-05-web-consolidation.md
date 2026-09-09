# Research Workbench Web 功能合并与运行监控

## 范围

本轮只交付 Web：Research Web、FastAPI、专属 DSH 3081、DataHub、会话与文件。没有运行、修改或验收 Tauri、macOS/Windows 安装包及桌面 sidecar。

## 已实施

- 新增“研究台”，覆盖市场、资产、基金、产业链、资料、报告六个二级页面；页面打开不联网，只有用户显式查询才访问 DataHub。
- 新增异步、幂等的研究台数据查询；真实数据形成会话隔离快照，状态与失败代码可查询。
- 新增页面到 FinGPT/Claw 的交接：先核对数据集归属，再逐文件复制并复核 SHA-256；页面上下文限制 64 KiB，不共享源会话路径，也不重复取数。
- 新增只读“运行与用量”，聚合 DSH 原生 usage、回合、子 Agent、工具、审批、DataHub 快照、服务健康及 Research Workbench 数据根占用。未知 usage 不记作零，模型价格未配置时不推算费用。
- 受管进程必须同时匹配状态文件、命令指纹、项目/数据根和实际 PID 命令签名；“进程存在”与实时健康仍为两个独立字段。
- 新增 CJPY/天软 Provider 边界：仅在依赖与终端配置齐备时可用；固定地址、受限能力、20 秒超时及 5,000 行上限。当前环境未安装/配置，目录如实显示阻塞。
- 将旧市场解读逻辑改造成 DSH 原生 `market-commentary` Skill 与步骤式 Workflow；不恢复旧报告编译、事实断言或第二套 Agent 编排。
- 更新 Research Web 当前架构 Markdown、API 清单及 Archify 的模块依赖、研究序列、DataHub/文件流三张图。

## 真实数据与页面证据

- 公开基金数据快照：东方财富 `aadf90ea-de16-4b49-9f25-4d3a806e9cbb`，10 行，截止 2026-09-04。
- 财联社快照：`d369d637-ffa5-4c98-a624-69b61c10e7be`，3 行；经新 `/api/research/data/queries` 异步接口生成。
- FinGPT 页面交接：`c8508492-1dd2-4f71-8668-e59d7533155b`，目标会话 `3504a20b-13ad-453f-b837-7e25f21892a2`，只复制上述财联社快照。
- 运行监控实际聚合：26 个会话、46 个回合、411,762 个已知 token，另有 4 个 usage 未知会话；8 个子 Agent、279 次历史工具活动、14 个 DataHub 快照。
- 服务状态分别返回 Web/DSH 的进程存在与健康检查；原有 3080 未被停止或改写。

## 验证

- Research Web Python：`319 passed, 3 skipped in 49.11s`。
- 新增研究台/监控聚焦回归：`7 passed`；覆盖幂等、选择性复制、无效数据集、超大上下文、敏感内容、单次历史加载及伪造/失配进程状态。
- JavaScript：137 项，`136 passed, 1 expected skip, 0 failed`。
- 本轮 Python 文件通过 Ruff、Black、isort；JavaScript 通过 Node 语法检查；`git diff --check` 通过。
- mypy 以 Python 3.12 检查本轮 CJPY Provider 未报错；全量仍有旧 `core/observability` logger 类型基线，未伪报全量通过。
- 架构一致性检查 `violations: []`。受影响 Archify 图均 showcase 9/9、零错误零警告，并完成 1440×900、1600×1000、1920×1080、2048×1320 视觉检查。
- 最终图源/HTML SHA-256：02 `b433cff3…` / `14b4471f…`；03 `48825849…` / `79edec64…`；04 `a1e3c23…` / `7466ee30…`。完整值保存在对应 receipt 与 `visual-review.json`。

## 合并与清理门禁

- 当前隔离验收 Web：`http://127.0.0.1:18088/`；3081 健康且用户已在设置页配置凭据。设置页经真实浏览器重新加载，完整显示且无控制台错误。
- 首次真实 FinGPT 提交被全目录门禁拒绝，原因是硬改名前持久能力版本仍含旧 Tool ID，且部分 Workflow 绑定已升级 Skill 的旧版本。新增失败回归后，目录按 Skill → Workflow 创建不可变后继版本；真实数据根 10 个已启用能力全部通过 selection 校验。
- FinGPT 会话 `3504a20b-13ad-453f-b837-7e25f21892a2` 已真实使用 `deepseek-v4-flash` 读取会话快照 `e988cbe3-d449-4689-a7e8-7c5f9293f3f9`，列出 3 条财联社记录，并明确来源、`as_of`、未完成分页和不联网限制；回合任务 `52bce86a9ba4c6d95e76dd89` 完成，文件交付为 `not_required`。
- Claw 会话 `cdbcf18c-955d-4941-9070-6af9e2df3a79` 已从 FinGPT 会话交接东方财富基金与财联社两个隔离快照；两个真实子 Agent `a867cf6a…`、`bd857a99…` 分别运行 47,054 ms / 26,157 ms，记录 16,805 / 13,903 tokens，并共用同一批资料而未重复取数。
- 同一 Claw 旅程实际生成并通过重开检查的 `fund000001_analysis.xlsx`（5 个工作表、60 个数值净值单元格）、DOCX、HTML、Markdown 和 XLSX 报告文件；这些产物来自真实会话输出目录，不是静态示例或历史文件误计。
- 全仓 `pytest -q` 仍受旧测试基线阻塞：`tests/research_web/test_api.py` 与 `tests/unit/test_api.py` 同名收集冲突，旧 ZQ 测试缺少可选 `Crypto`。本轮不安装无关依赖；Web 合并门禁使用隔离的 `tests/research_web --confcutdir=tests/research_web`，并单独记录旧基线。
- 在真实 FinGPT/Claw、文件交付、停止/审批/恢复门禁通过前，不合并 `master`，不推送迁移标签，也不删除 worktree、旧目录或构建产物。
- 已保护外部 runtime core 未提交源码：分支 `codex/archive-runtime-core-20260905`，提交 `7a10e07`。完整历史 bundle 已写入 `~/.research-workbench/migration-backups/runtime-core-20260905.bundle`，校验通过，SHA-256 为 `10ad84253b482f3b6a7b612482dc7e541b83ba7f738c109b8553698df9254807`。
