# RWB MCP 私网只读首版实施记录

任务：`rwb-mcp-readonly-oauth-20261104`。宿主 macOS / Mac mini；类型为 Web 功能开发，验收范围为本机隔离验证及适用同平台安装 CI。Windows/Linux 产品验证、常驻服务、真实账户授权和生产数据迁移不属于本次自动执行范围。

## 身份与状态

- 基线：GitHub 与共享 Git 对象均确认 `87b6cd99653d9f8160dc7eb0b3bea8d5d9ea93db`。
- 工作区：Codex 原生登记的独立 `codex/mcp-readonly-oauth-stage` 分支；原工作区未修改。正式 GitSafety start 因 GitHub SSH 认证失败而未创建交付回执。不能以原生工作区替代正式发布流程。
- 授权存储已提交 `0c00e6bd14a6bb0e57d383d90b6cdb06c78b6900`；独立 Python/规格评审 Approved。四项工具、HTTP 集成、全量适用 Router、同候选 CI 与最终交付尚待完成；本记录会随真实证据更新。
- 常驻更新、Codex 私网双设备实链、官方 DSH 与 WorkBuddy 原生 OAuth：`NOT_RUN`；本地通过不提升这些状态。

## 已冻结合同

见 [入站 MCP 合同](../../docs/research-web-mcp-facade.md) 及 [实施计划](../../docs/superpowers/plans/2026-11-04-rwb-mcp-readonly-oauth.md)。仅开放四项批准冻结材料的读取工具；固定原生公开客户端、PKCE、持久摘要授权和逐对象权限。保留 DSH/DataHub/Provider/质量门，FinGPT/Claw 的通用执行能力停止扩建，既有入口不退役。

## 只读与 SDK 核验

源码定点核验表明，普通文件列表会写入文件索引，来源读取在缺档时可能抓网；新 facade 必须避开两者。原 manifest 字节摘要、行文件摘要和文本片段摘要分别表达，不将 URL 增补后的 JSON 当作原 manifest。

锁定 SDK 为现有 `mcp==2.2.0` / `mcp-types==2.2.0`。原生 `MCPServer` 可用，FastMCP 不适用；SDK 的 token resource、公开客户端元数据和授权响应 issuer 需要薄适配及真实 HTTP 负例。没有升级或修改 SDK。

## 测试环境与事故保留

首个环境存在 SDK 但没有 pytest，`store-red` 实际退出 1；该结果是环境失败，不能当行为 RED 或 PASS。未安装依赖。随后验证另一已有环境同时具备锁定 SDK、pytest 和检查工具；通过显式 `PYTHONPATH` 验证 app/core 源码指向本任务工作区，不执行历史产品源码。

初次没有生成业务夹具的临时根按原 lease/nonce/批次/节点恢复：容量检查、真实 pytest、输出哈希及正式 retire 完整执行。`store-red-recovery-01` 得到一个明确预期的 `XFAIL`，只证明尚无授权存储实现，不能当业务验收。原环境失败输出和结果保留，没有伪造退出码、删除未知临时根或覆盖回执。后续 GREEN 必须去除预期失败标记。

Task1 WIP：16 项授权存储测试、17 项既有账户回归和 3 项后补边界测试通过；Ruff、Black、isort、Mypy 和 diff 检查通过。独立评审复核规格、事务和日志边界，没有重跑行为测试。这些回执不代表 exact-SHA、HTTP 或 CI 验收。

任务日志位于 `logs/rwb-mcp-readonly-oauth-20261104/`，最终须生成逐文件保留清单。最终候选认证将在完成后补入，不预填结果。
