# Hot / 研究情报接续记录

宿主 macOS，任务类型功能开发。目标仍为原 Goal 的阶段 0–5，未完成任何门不降级。

## 断点与保全

- 原 worktree：`/Users/leon/.codex/worktrees/hot-events-system/ResearchWorkbench`。
- 原分支：`codex/hot-events-system-20261007`；候选 `fc60414f6c38a0a9e677a8d137c397a0c1895373`。
- 原权威记录：`2026-10-07-hot-events-PROGRESS.md`，完整历史保留；本文件接管后续动作与状态。
- 应用重新绑定被拒绝：原 worktree 属于另一个聊天。未修改原目录或向原聊天发消息。
- 本次 worktree：`/Users/leon/.codex/worktrees/hot-intel-continuation/ResearchWorkbench`。
- 本次分支：`codex/hot-intel-continuation-20261012`。
- 原 5 个已跟踪改动及 3 个新增文件已通过 Git binary patch 恢复，8 文件逐字节一致；原 Git 状态未变化。
- 保全证据：`logs/hot-resume/resume-receipt.json`；补丁 SHA256 `b8103eecebb5d4865420231338f71c5f2e4cb1136860d70422117a74dea3662c`。
- 恢复后使用当前 Mac 主项目已有 `.venv/bin/python` 执行 DOCX unittest：5/5 PASS，未安装依赖。仅验证旧 WIP 的局部行为，不认证完整导出路径。

## 最新主线与融合决策

- GitHub API 核对：PUBLIC；最新 master `8a2d4ba75294b3fbe2aa90aa802dfd25a1296a2b`。
- PR #92 已合并：只读资讯雷达，固定 Golddata GET API，8 栏目；没有本地材料库、worker 或模型执行。
- Hot：Node/TS + PostgreSQL + pg-boss，独立版本材料/事件/频道/简报，受控 FastAPI 桥；现有真实两材料/两简报证据保留。
- 用户明确选择统一入口，并要求命名。采用名称建议“研究情报”：本地热点与事件 + 现有外部资讯栏目。
- 页面共用入口与主题；本地/外部数据始终标明来源，保留独立事件身份与覆盖边界。外部列表不直接写入 Hot 或冒充本地材料证据。
- 原 Hot API/CLI、唯一队列和数据库所有权保留；外部 GET 不创建采集任务/模型调用。
- `#/workbench/hot` 与现有 `#/intel/*` 旧链接继续可解析；新导航归研究情报。
- 实现顺序：保全 WIP → 合入最新 master → 路由/导航融合 → 本地相关回归 → 继续原阶段四及其余验收。
- merge-tree 三方预览提示 26 冲突文件，以 UI 路由、文档与生成物为主；日志 `logs/hot-resume/merge-preview.log`。预览不是实际合并完成。

## 未完成与授权边界

本平台验收仍 NOT_RUN/BLOCKED，整体 NOT_READY。DOCX 正式导出/跟踪/研究交接、真实 DSH、持续采集重验、留出样本、联合恢复、Mac Docker、干净安装与 exact-SHA Mac CI 均未由本次认证。Windows/Linux 为设备交接。无生产部署或合并主线。

旧记录中的累计付费预算不得重置；本次尚未读取权威预算或验证授权，不发付费调用。后续先核对原授权、账本与有效状态，再使用剩余额度。无外部发送。

下一步：合并最新主线并实现统一导航，保留 Hot 的业务合同和外部雷达只读边界。
