# 2026-09-03 能力包与版本后端

工作树 `.worktrees/dsh-web-v1` / `codex/dsh-web-v1`；起始 HEAD 9471e4a。
所有权限定 `capabilities/`、后端接线、focused Python/native tests 及本说明。
未编辑 UI、架构主入口、CI、模型、权限或执行限额；未重启 live 实例、调用模型、安装依赖、推送或发布。

## 实施与证据

- 首轮 TDD：`test_capabilities.py` 15 项先失败（缺 API，404）；实现后 15 passed。
- 第二轮：`test_capabilities_admission.py` 初次 6 failed/7 passed：缺详情版本、停用后幂等重试、创建用途、资源哈希校验；修复后 13 passed。补充自动 Skill 快照及创建 ZIP 2 项先失败，修复后 15 passed。
- 原生固定源码：`test_capabilities_native.py` 真实 FileSystemSkillProvider list/get/watch 及默认根排除；真实工具注册对照先发现漏列内部 report，再补齐（不新增权限）；2 passed。
- 安全补充：`test_capabilities_safety.py` 初次 6 failed/1 passed，覆盖安装钩子、安装代码、目录 symlink、版本详情、非法 base64；修复后 7 passed，另核验嵌套 YAML 拒绝、持久化 pending 启动拦截和 Workflow 关联版本。
- 测试过程中发现 macOS 只读目录跨父级移动报 PermissionError：仅原生投影顶层保持服务私有0700，版本树/文件及会话资源仍只读。
- 静态 mypy 25 个源文件检查通过；项目默认 untyped 函数检查范围有既有 notes，不把其称为完整强类型证明。
- 完整 research_web suite：158 passed in 26.10s，含固定源码 native tests。
- 自审补充旧版幂等收据回归：升级前 digest 的同键重试最初 400 失败，增加只读旧收据兼容后通过，不重复提交模型；最终能力聚焦 40 passed。
- 最终 `ruff check app/research_web tests/research_web`、`black app/research_web tests/research_web --check`（41文件）、`isort app/research_web tests/research_web --check-only`、`mypy app/research_web --exclude '/skills/' --follow-imports=skip` 全部通过。
- `git diff --check`、`python scripts/check_task_completion.py` 通过；`python scripts/check_doc_sync.py` 退出0但报告 No source files requiring doc sync were changed：既有检查未覆盖本新模块，不宣称架构同步已验证。
- 整套158项是在最后旧收据兼容之前执行；最后改动后重新执行全部40项能力聚焦与上述静态检查。最终主控制器可执行集成总回归。

所有 pytest 使用当前 macOS 既有环境 `/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python`；
原生测试 `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness`，固定 commit b150a551b8d465e31e418e1b2eaf5e79bbb7d28e。
聚焦命令格式：`python -m pytest tests/research_web/test_capabilities*.py --confcutdir=tests/research_web -q -o addopts='' --tb=short --show-capture=no`。
`-o addopts=''` 恢复 pytest capture，避免仓库 `-p no:capture` 产生巨大终端日志，不改变测试内容。

## 变更—证据映射

| 变更 | 测试 | 文档 |
| --- | --- | --- |
| 元数据、导入、安全检查、版本、种子 | test_capabilities.py / test_capabilities_safety.py | docs/research-web-capabilities.md |
| API、互斥受理、资源快照、创建会话与产物 | test_capabilities_admission.py / existing test_api.py | 同上 API、会话与安全章节 |
| 工具只读投影、启动器、native watch | test_capabilities_native.py | 同上原生接线章节 |

## 交接与限制

完整契约在 `docs/research-web-capabilities.md`。GET /capabilities 离线读取，工具目录是声明而不是在线授权。
消息 capability_id/capability_version/tool_ids；显式 expected_formats 优先；创建会话返回未发送 draft。
发布/停用/回滚与发送共享服务锁；活动/未知状态拒绝变更并保留草稿。
自建版本 native_name 带版本号；旧版本仅查看/导出，使用必须显式回滚；不会改写旧会话资源。

需主控制器在空闲后更新授权专属启动配置：native skill root 改为 `<data>/capabilities/native-skills`，
watch=true、includeDefaultRoots=false、watchFollowSymlinks=false。未更新旧 live 实例时，新包原生发现会明确失败。
尚未执行：新能力 UI 浏览器旅程、真实创建/发布/调用、真实 Workflow；这些由主控制器集成验收。
架构图、source映射和最终Harness门禁由主控制器任务持有，本子任务不代替其最终验收。
导入静态检查不是恶意代码形式证明，资源只在既有严格沙箱通过现有工具使用；无新增权限。
崩溃留下 pending 时 fail closed，需操作者停止专属实例后审查恢复，不自动抹除不确定状态。
