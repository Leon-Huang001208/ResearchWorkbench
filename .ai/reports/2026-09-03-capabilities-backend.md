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

## Task 2 独立审查聚焦修复（基线 076be7c）

按 bugfix-minimal / TDD / ship-check，限定两个既有源码模块、一份新回归文件与本模块文档/报告。
未修改 UI、控制器架构图文或接线配置；未重启 live、调用模型、安装依赖、递归委派、推送。

| 审查问题 | 修复 | 回归证据 |
| --- | --- | --- |
| 自主发现目录绕过依赖/Workflow 版本检查 | snapshot_catalog 先对整个启用集合复用 selection，再复制资源；失效包明确拒绝发送，不静默跳过 | 无显式选择时依赖卸载、关联 Skill 升版均拒绝；无 session.prompt/新目录快照 |
| 图片/PDF 仅看扩展名、magic 不完整 | 有界容器证据检查 + 补齐空 ZIP/Mach-O/XZ 等特征；不渲染/解压/执行 | 6 类扩展名 × 5 类伪装；ZIP 导入问题保留、合法六类样本、截断/伪头/未知 XML 编码 |
| 文件/目录前缀冲突与部分版本写入 | 草稿和 ZIP 空目录双向前缀检查；隐藏 staging 构造后再提交/封存，失败保留草稿、旧版和暂存证据 | 两种顺序、大小写、元数据路径、空目录；write/promote/seal 三类故障后重载并成功重试，旧版本字节不变 |
| 回滚历史名称/slug 与其他能力冲突 | 在目录切换前对目标历史元数据复查唯一性 | name/slug 两类409；版本、原生目录、重载索引均保持原状态 |

TDD 实际过程：新增 test_capabilities_review.py 首轮 **38 failed / 4 passed**，四项问题均复现。
第一实现轮 **1 failed / 30 passed / 11 errors**：实测 macOS 同父目录重命名仍要求源目录可写，
且测试 PNG 的 IDAT CRC 本身错误；修正临时目录移动顺序及样本 CRC 后 **42 passed**。
相邻边界补充（ZIP 空目录冲突/GIF 伪头）**3 failed / 44 passed → 51 passed**；
未知 XML 编码另获 **1 failed / 50 deselected**，纳入 LookupError 明确拒绝后通过。
合法 JPEG/GIF/WebP 固定测试字节由既有本地 Pillow 内存生成；测试和生产校验都不依赖 Pillow，未新增依赖。

实际命令（均使用上述既有 Python）：

- `python -m pytest tests/research_web/test_capabilities_review.py --confcutdir=tests/research_web -q -o addopts='' --tb=short --show-capture=no`：最终 51 passed。
- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web/test_capabilities*.py --confcutdir=tests/research_web -q -o addopts='' --tb=short --show-capture=no`：91 passed in 7.45s（未知 XML 编码补充前）。
- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q -o addopts='' --tb=short --show-capture=no`：**210 passed in 25.13s**，含未知 XML 编码修复及原生 provider/注册测试。
- `python -m ruff check app/research_web tests/research_web`：首轮一个 SIM102 风格问题，合并条件后通过；无语义变更，随后重跑51项聚焦。
- `python -m black app/research_web tests/research_web --check`：42 files unchanged；`python -m isort app/research_web tests/research_web --check-only` 通过。
- `python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip`：25 source files 通过，既有 untyped notes 保留，不宣称全强类型覆盖。
- `python scripts/check_task_completion.py`、`git diff --check` 通过；`python scripts/check_doc_sync.py` 退出0，但仍未覆盖本模块，不作为全局架构已冻结证据。

API 路径/输入未变：发送可返回 blocked_dependencies / linked_version_conflict；导入 checks 新增
invalid_media / path_conflict；冲突回滚409 name_conflict，版本写入异常503 publication_failed。
前端不应吞掉这些错误或把仍可原生发现的失效能力说成已自动跳过；可提示停用/修订再发布。

剩余边界：容器证据不等于完整解码或恶意资源安全证明，依然只按现有沙箱权限使用；暂存文件保留供审查，
不会自动删除用户数据。写入失败正常恢复可重试；撤回失败则持久化 pending、fail closed、由操作者恢复。
本次不新增启动变化；前一实现的产品专属 skill root/watch 仍待控制器按授权在空闲后接线。
真实模型/UI、全局架构门禁及 Harness 最终验收依然由控制器负责。

控制器追加冷恢复预检：固定 DSH 源码 `packages/preset/agent-presets/src/session.ts` 只记录/解析 preset ID，
`packages/host/apiproxy/src/api-proxy.ts:1199` 冷恢复通过 composeAgent；
`packages/preset/agent-presets/src/index.ts:491` ensureStanding 按当前文件（mtime/size）创建 generation。
仍活跃的 Agent 保留旧 generation；真正冷恢复读取记录 ID 当前指向的 preset，而非序列化整份旧root配置。
Web skill_catalog 已用 session.models 冷恢复后 skill.list exact-name检查，缺新增能力409 native_discovery_pending。
未重写会话历史/preset，未执行真实跨重启旧会话实验；该结论区分源码机制与未验证的live行为。
控制器显式新建/升级Claw复用旧FinGPT材料仍是可观察的集成路径，前端可在持续缺发现时提示此方案。
