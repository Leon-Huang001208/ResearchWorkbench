# leon-engineering 共享验收内核接入回执

## 范围

- RWB 基线：`master` / `4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7`。
- leon-engineering：0.19.3 / `b44e6630eef64e93f14feafdc2501b243935a8c5`（已发布 `main`，CI passed）。
- 接入方式：`.agents/runtime/leon-engineering/` 的 manifest-owned 最小运行时。
- 项目继续拥有 `.agents/verification-policy.json`、业务映射、平台支持和必需门。
- 未修改 `app/`、`src-tauri/`、`desktop/`、安装器、workflow 或其他产品源码。

## 兼容与验证

- 接入前 current-master 策略、回执与 Skill 合同：85 passed。
- 平台 schema-v3 / receipt-v2 合同移植后：87 passed。
- 共享 runtime 薄入口接管后，planner、receipt 与 Skill 合同：93 passed。
- runtime `preview → install → upgrade → verify` 均在隔离 worktree 完成；最终 manifest verify 为 `valid: true`、`drift: []`。
- 完整 24-file changed set 规划为 `full-delivery/L4`，已知规则为 verification-system、schema 与 documentation，`uncoveredRisks: []`。

受管 manifest 记录 policy 3、plan 3、receipt 2，以及 11 个 runtime 文件的 SHA-256。安装和升级私有回执保存在 Git common 目录，未提交本机绝对路径。

## 未执行与边界

- 未 push、未创建或合并 PR、未 dispatch workflow、未发布。
- GitHub CI、原生 Windows、真实 Windows 安装和真实 Codex/Claude 宿主加载均未执行。
- 平台分支中的 workflow、launcher、`service_manager.py` 和产品修复未带入本接入。
- `architecture-review: structure unchanged`：产品模块拓扑未变化；新增内容只属于工程 runtime、策略、薄入口、合同测试和工程文档。
