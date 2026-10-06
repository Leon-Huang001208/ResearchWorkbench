# 平台验收职责修订

hostPlatform: macos
taskKind: documentation
hostAcceptance: PASS（隔离工作区文档任务 L0）
aggregateAcceptance: PASS（隔离工作区本次文档变更）；主工作区治理 FAIL

本任务仅修订治理文档，不进行产品功能开发、平台适配或 CI 配置变更。

## 平台职责

- MacBook Pro：项目功能开发、macOS 适配与本地验收、GitHub macOS CI。
- Windows 真机：既有功能的 Windows 适配、本地验收、GitHub Windows CI；不承担功能开发。
- Linux 真机：既有功能的 Linux 适配、本地验收、GitHub Linux CI；不承担功能开发。
- 他平台验收交接不阻塞当前宿主任务；跨平台发布就绪仍要求各目标平台真实证据。

## 执行边界

已同步 AGENTS、Agent 路由、README、安装指南、桌面指南、Actions 治理及 README review。总体验收规划器和回执校验器仍无宿主参数；本次通过任务路由与分平台报告约束执行代理，未宣称机器校验已实现宿主范围。总计划不得删门，未运行项不得伪报 PASS。现有 workflow 触发、runner 和支持矩阵未改动。

platformHandoffs: []（本次为文档修订，不产生产品平台适配任务）

## 验证

执行结果将由同目录 verification receipt 与 logs/platform-acceptance-20261006/ 保存。未执行远端 CI、Windows/Linux 真机验收，不声明任何新增平台支持；文档任务是否需要 CI 由完整 changed set 的计划决定。

主工作区文档治理未通过：208 项现存虚拟环境备份中的未分类 Markdown。详见 logs/platform-acceptance-20261006/documentation-governance.log；不删除备份、不放宽治理规则。后续隔离工作区检查与主工作区失败分别记录。

隔离工作区实测：文档治理、Python 文件索引、19 项文档/Actions 合同测试、项目约束、git diff --check 全部通过。完整 changed set 的 L0 计划无 CI 或真机门；本次无需产品 macOS bootstrap。验证位置：/Users/leon/.codex/worktrees/platform-acceptance/ResearchWorkbench。未提交或发布。

## 发布合并补充

本次在远端 master 05326b6066f96a572db4ac87f3bdc041ff92003f 上三方合并，保留新增 Git/设备、Docker/Native 与 exact-SHA Windows CI 路由。发布使用独立分支、受管集成与 PR；提交前本地复核，远端 CI 状态记录于受管 delivery receipt，不预先宣称通过。

最新远端基线合并复核：文档治理、生成 Python 索引、28 项文档/额度/跨平台仓库合同测试、完整 changed set 项目约束与 git diff --check 通过。日志位于主 checkout 的 logs/platform-ownership-ship-20261006/。产品平台 CI 未执行，不代表 macOS/Windows/Linux 产品已验证。
