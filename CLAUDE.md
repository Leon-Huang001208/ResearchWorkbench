# Claude Code additions

@AGENTS.md

`AGENTS.md` 是共享规则真身。本文件只保留 Claude Code 专属差异，不复制项目架构、命令或平台验收规则。

## Claude-specific workflow

- `.claude/` 是本机可选配置；其缺失不得阻塞仓库工作，也不能作为共享规则来源。
- 视觉或交互改动需要截图时，可使用当前会话可用的浏览器工具保存实际证据；未执行的浏览器检查不得写成通过。
- Claude 子 Agent 仅用于边界清晰的只读探索或验证。仓库编辑仍必须遵守 `AGENTS.md` 的 worktree、交付和平台规则。
- 当前产品、启动方式、源码归属和文档入口统一从 `README.md` 与 `docs/README.md` 获取，不在本文件维护第二份快照。
