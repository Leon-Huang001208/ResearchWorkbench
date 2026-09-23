# Research Web Mac-only 自动验收设计

## 背景与目标

Research Web 当前同时在 GitHub `macos-14` 与 `windows-2022` runner 上自动执行干净安装和启动验收，另有一条自动 Windows local integrations workflow。Windows 后续改由用户在装有 Windows 的实机上验证；GitHub 自动交付暂时只保留 macOS。

本次调整必须满足：

1. 本机 Mac 验证通过后，仍必须运行 GitHub `macos-14` 干净环境验收；本机结果不能替代远端结果。
2. GitHub 不再因 PR 或 `master` push 自动启动任何 Windows runner。
3. 已有 Windows workflow 与验证逻辑不删除，只暂停自动触发，便于人工调度或以后恢复。
4. 暂停期间不得把未运行的 Windows 验证表述为已通过。

## 选定方案

采用“Mac 自动门 + Windows 手动保留”方案。

- `.github/workflows/research-web-bootstrap.yml` 由 macOS/Windows matrix 收敛为单个 `macos-14` job，保留现有 `pull_request`、`push master` 和 `workflow_dispatch` 触发。
- `.github/workflows/research-web-windows-verify.yml` 移除 `pull_request` 与 `push` 触发，只保留 `workflow_dispatch`。workflow 内容继续保留，不计入默认交付门。
- `.agents/verification-policy.json` 保持稳定 gate ID `research-web-bootstrap`，但其值明确指向 macOS job；安装、依赖、DSH、CJPY 与启动链变更仍必须进入该外部门。
- Windows 实机验证由用户独立执行。除非用户提供本次实机回执，项目报告只能记录为“由用户负责、当前未纳入自动门”，不能推断通过。

不选择以下方案：

- 删除 Windows workflow：会丢失已经验证过的脚本和恢复入口。
- 使用仓库变量动态启停 Windows matrix：引入不可从仓库内容审计的隐式状态，不利于 verification receipt 复核。

## 文件与职责

### Research Web Bootstrap

`research-web-bootstrap.yml` 是 Web 安装与启动链的自动平台门。调整后它只负责：

1. 在 GitHub `macos-14` 干净 runner 上执行公开安装入口；
2. 验证项目 Python 环境、CJPY 与固定 DSH；
3. 启动 3081/8088；
4. 验证 Doctor、HTTP 与无凭据 Tinysoft 投影；
5. 清理服务并保存最小成功或失败证据。

本机 Mac 验证与该 workflow 是串联关系：本机先提供快速反馈，GitHub Mac 再提供干净环境和远端执行证据。

### Windows Verify

`research-web-windows-verify.yml` 保留现有 Windows contract、UI contract、loopback smoke 与工件上传实现，但默认不运行。它只有人工 `workflow_dispatch` 入口，不出现在 Research Web 默认 verification gate 中。

Windows 实机验证由用户负责，其结果与 GitHub workflow 状态分开记录，避免把“具备手动能力”误写为“已经验收”。

### Verification policy

`research-web-bootstrap` 继续是 `external`、`L4` gate。涉及 Web 安装、启动、锁定依赖或运行时闭包的变更，即使本机 Mac 全部通过，receipt 在 GitHub macOS gate 返回成功前仍必须保持 blocked。

此次暂停不影响桌面端规则。未来若明确重启桌面工作，`native-windows-desktop` 等桌面专属门仍按桌面政策单独处理。

## 失败处理与证据

- GitHub macOS Bootstrap 失败时，交付保持 blocked，并读取该 run 的日志与工件；不得以本机 Mac 成功降级绕过。
- Windows 自动 workflow 不应因 PR 或 push 出现新 run；若人工 dispatch，则按实际结论记录，但不改变默认 Mac gate。
- 用户未提供 Windows 实机回执时，报告明确写“未在本次自动交付中运行”。
- 工作流、策略或测试不一致时，Project Constraints/verification policy contract 必须失败关闭。

## 验证设计

实现后的最小充分验收包括：

1. workflow contract：Bootstrap 只包含 `macos-14`，且仍含 PR、`master` push 和手动触发；Windows Verify 只含手动触发。
2. planner contract：安装/启动链变更仍产生 `research-web-bootstrap` 外部门，且 gate 值明确指向 macOS。
3. 本地相关测试、Project Constraints、格式与文档治理通过。
4. 发布后 GitHub Project Constraints、Research Web Checks 与 macOS Research Web Bootstrap 均成功。
5. GitHub run 列表中不产生由该提交自动触发的 Windows job。

## 回滚

恢复 Windows 自动验证时，重新把 `windows-2022` 加入 Bootstrap matrix，并恢复 Windows Verify 的 PR/push 路径触发；同步更新 verification policy、contract tests 和安装文档。不得只在 GitHub UI 中改变量或临时开关。

## 非目标

- 不删除 Windows 验证代码。
- 不宣称 Windows 实机兼容性已由 Mac 或 GitHub Mac 证明。
- 不修改桌面/Tauri/sidecar 的当前阶段边界。
- 不借此调整 Research Web 运行时超时、依赖版本或产品功能。
