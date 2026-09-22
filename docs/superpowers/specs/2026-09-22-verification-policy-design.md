# ResearchWorkbench Verification Policy Design

## 目标与边界

ResearchWorkbench 需要根据仓库相对改动路径生成机器可读的最小验收计划，并在风险不能被证明为低时升级到 `full-delivery`。规划器只读取项目、策略和路径元数据；它不运行测试、Git、CI、发布命令，也不创建日志或其他产物。策略真源唯一为 `.agents/verification-policy.json`，`.claude/commands/verify-task.md` 仅作为薄兼容入口。

当前产品阶段为 Web-only。仅命中 `app/research_web/` 或 `app/web/` 的普通 Web 改动只能获得 Web、文档与轻量 CI 门，输出中不得包含 desktop、Windows、Tauri、sidecar 或 installer 门。公开契约、schema、依赖、CI、安全、桌面、发布和未知路径始终升级到 `full-delivery`；其中只有桌面路径附加原生 Windows 与 desktop packaging 门。

## 数据合同

策略文件使用严格、版本化 JSON，顶层只允许 `schemaVersion`、`riskOrder`、`catalogs`、`rules` 与 `fallback`。`riskOrder` 固定为 `docs-only`、`local-only`、`full-delivery`。`catalogs` 分为 `tests`、`documentation`、`ci`，每个条目把稳定 ID 映射到非空命令或 workflow 路径。规划器只复制这些字符串到输出，绝不解释或执行。

每条规则只允许 `id`、`risk`、`reason`、`match`、`tests`、`documentation`、`ci`。`match` 只允许 `files`、`prefixes`、`segments`、`suffixes` 四组字符串。一个文件可以命中多条规则；其风险取最高档，门集合按目录和首次出现顺序去重。无规则命中的文件使用 `fallback`，风险必须是 `full-delivery`，原因码固定为 `unknown_path`。

成功输出固定包含：`schemaVersion`、`risk`、去重后的 `changedFiles`、逐文件 `reasons`、`tests`、`documentation`、`ci`。门条目为 `{id, value}`。错误写入 stderr 的单行 JSON，固定包含 `schemaVersion`、`error.code`、`error.message`，并以非零状态退出；稳定错误码包括 `ARGUMENT_ERROR`、`PROJECT_ERROR`、`PATH_ERROR`、`POLICY_ERROR` 与 `INTERNAL_ERROR`。

## 路径与文件安全

`--project` 必须指向真实普通目录且参数自身不得为符号链接。每个重复的 `--changed-file` 必须是非空、无控制字符、无反斜杠、非绝对、规范化后仍在仓库内的 POSIX 相对路径。规划器去重后检查从项目根到目标的每个已存在组件；任何符号链接都返回 `PATH_ERROR`。允许目标文件不存在，以便规划删除改动，但已存在组件必须保持在真实项目根内。

策略路径固定为 `.agents/verification-policy.json`，其所有组件必须存在、不得为符号链接，最终对象必须是普通文件。JSON 解析后逐层执行 exact-key、类型、非空、引用完整性、唯一 ID、风险顺序及 fallback 风险校验；损坏、弱化或未知字段均返回 `POLICY_ERROR`，不产生降级计划。

## 路由语义

文档路径只合并文档治理、生成索引和 Project Constraints，不安排 Web 或桌面测试。普通 Web 路径合并 Research Web 架构测试、文档治理、生成索引、Project Constraints 与 Research Web Checks。契约、schema、依赖、CI、安全和发布规则只负责把风险提升到 `full-delivery` 并合并各自相关门，不隐式追加桌面门。

桌面专属路径为 `src-tauri/`、`desktop/`、`scripts/desktop/`、`services/desktop_platform/`、`data_layer/adapters/wind/` 与 `core/settings/`。它们必须输出 `full-delivery`，并包含 `desktop-packaging` 文档门及 `native-windows-desktop` CI 门。未知路径同样 `full-delivery`，但不能伪称已识别为桌面改动。

## Project Constraints 与兼容入口

`.agents/project-constraints.json` 保持现状，不承载策略或规划器清单；策略、规划器、测试与兼容入口由本次受管交付和各自合同直接保护，避免用虚假的 changed-file 参数绕过现有门禁。受跟踪的 `.claude/commands/` 由 `docs/documentation-governance.json` 分类为 `package-internal`，并同步 documentation 架构组文档与 `structure: unchanged` 回执。`verify-task.md` 只展示重复 `--changed-file` 的调用方式、说明读取 JSON 计划后逐项执行，并声明策略真源；它不复制路径、风险或门表。

## 验证与交付

测试先通过真实 CLI 冻结纯 Web、文档、七类高风险、桌面、未知、去重合并、非法 JSON、策略/改动路径符号链接、越界路径、稳定错误码和“不执行目录中命令”的合同。实现前必须记录因规划器不存在而产生的预期 RED；实现后同一测试必须 GREEN，且原 62 项架构测试不退化。

本次变更影响验收与 CI 路由，必须经受管 `iteration-delivery` 完成 feature worktree 提交、`prepare`、integration worktree 全量复验、`publish`、CI `status` 与安全 `cleanup`。任何未验证平台或外部状态必须留在 BLOCKED，而不是写成通过。
