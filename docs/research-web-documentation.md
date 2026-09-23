# Research Web 文档门禁与安全入口

Web 安装契约另由 `.github/workflows/research-web-bootstrap.yml` 提供 GitHub `macos-14` 干净安装、
固定 DSH 构建、3081/8088 启动、Doctor 和无凭据天软断言证据；Windows Web 证据在用户完成 Windows
实机验证后单独提供，详见 [Research Web 安装契约](research-web-installation.md)。
`.agents/project-constraints.json` 校验其平台、公开 setup 入口、Doctor、CJPY 和无凭据天软断言。
它不替代本页的架构映射、回执、截图和人工审阅门禁。

## 模块边界

`scripts/check_research_architecture.mjs` 是 Research Web 图文映射的离线检查核心；
`scripts/check_documentation_governance.mjs` 校验全部 Markdown 的状态分类、主题权威、当前链接和退役命令。
`scripts/check_doc_sync.py` 组合上述检查与 Python 生成索引校验；`.agents/project-constraints.mjs` 保留架构与平台约束。现有
`.github/workflows/project-constraints.yml` 先运行架构／治理负向 fixtures 与 Tabbit 手动触发契约，再检查真实变更和清单。
不要求开发机绝对目录、Archify 安装、模型服务或网络，不生成或篡改回执。

`.agents/verification-policy.json` 与 `scripts/plan_verification.mjs` 负责把完整 changed set 映射为最小验收计划；规划器只输出 JSON，不运行其中的测试、Git、CI 或发布命令。`.claude/commands/verify-task.md` 是受跟踪的薄兼容入口，按 `package-internal` 分类，只调用项目规划器，不复制路由表。Project Constraints 继续负责架构、平台和文档硬门，不承载这份路径策略。

Actions 触发与免费额度以 [GitHub Actions 额度治理](actions-budget.md) 为准：Project Constraints 和普通 Research Web 回归使用 Ubuntu；Bootstrap、Windows、Tabbit 与 Desktop 只在各自边界触发。额度达到冻结状态时，本地门禁仍可运行，但不得创建远端 Actions run。
Ubuntu 日常回归使用有界 Python 合同集和 `research_web*.test.mjs`；全量 `tests/research_web/` 仍按变更风险在本地交付阶段运行，不把长耗时全量套件伪装成便宜的 push 门禁。

输入契约见 [当前架构契约](architecture/research-web/06-documentation-contract.md)，
清单见 [architecture-map.json](architecture/research-web/architecture-map.json)。
最终必须包含 01–10 十图，不能用部分完成状态跳过门禁。其中 09 是报告运行序列，10 是 Excel 刷新、共享快照与文件组装数据流。

根 README 另由 [README 复核回执](architecture/research-web/readme-review.json) 记录本轮
`updated` 或 `unchanged` 决策。`.agents/project-constraints.json` 将 Research Web、CLI、公开入口和
两份包清单声明为触发范围；触发后必须把回执放入完整 changed-file 集。回执严格限制为四字段
schema 1，且必须是仓库内普通 JSON 文件。`updated` 要求同批包含 `README.md`，`unchanged`
只需写明非空摘要和具体原因。根 README 同时进入现有本地 Markdown 断链检查。
该配置块本身不可缩减或重定向：README、回执、三个目录前缀和两份包清单都与检查器固定常量
做集合等价校验；仅数组顺序可变，空、缺失、额外、重复或替代路径均失败。

## 本地命令

```bash
node --test tests/javascript/research_web_architecture.test.mjs
node --test tests/javascript/documentation_governance.test.mjs
node --test tests/javascript/actions_quota_governance.test.mjs
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
node scripts/check_research_architecture.mjs --project . --base <git-revision>
python scripts/check_doc_sync.py --project . --base <git-revision>
node .agents/project-constraints.mjs --project . --changed-file app/research_web/main.py
```

Node/Python 命令均接受重复的 `--changed-file`。没有显式文件列表时读取 Git staged、
unstaged 与逐文件 untracked；`--base` 还包括该 revision 到 HEAD 的变更。错误 Git
revision、仓库缺失、回执无效会失败，不能当作空变更通过。离线非 Git fixture 可使用
显式文件列表或 Node `checkResearchArchitecture({projectRoot, changedFiles})` 函数。
显式文件列表应完整覆盖任务，不是用来隐藏实际改动的豁免。
Project Constraints CI 先将 `git diff -z` 成功结果保存到临时文件，再以 NUL 分隔读入完整文件名；
Git 失败立即停止，不让 process substitution 的退出状态丢失后继续检查零个变化文件。

## 检查内容与核对标记

- 所有 Research Web Python、JS/MJS、CSS、HTML、Skill Markdown/脚本/模板与配置均检查映射。
- 映射的源码、模块 Markdown、测试、图节点和关系证据必须存在且不经过符号链接。
- 清单顶层必须为非 null 对象；`null`、布尔值、数字、字符串和数组均失败，不以空违规列表返回。
- 扫描源码中的 HTTP 装饰器及 APIRouter 前缀，双向比较接口 inventory；新增遗漏和旧接口均失败。
  HTTP 装饰器接受位置参数或 `path=` 字面量，含换行和其他参数在前的形式；动态路径、转义路径及
  不支持的 `api_route`/`route`/`websocket` 声明明确报 `api_declaration_unsupported`，不静默漏检。
- 变更组的每份模块说明和本次 `.ai/reports/*.md` 任务报告必须出现在变更清单；任务报告含明确结构决策。
- 图源、HTML 的实际 SHA-256 和字节数必须匹配 deliver；要求 showcase 9/9、零错误零警告。
  HTML、deliver 回执和视觉回执还必须使用根目录内按十图 ID 固定的规范文件名；
  `../`、非规范别名和其他文件名在读取前即被拒绝。
- 视觉回执必须绑定当前 HTML，四个固定视口 1440×900 / 1600×1000 / 1920×1080 /
  2048×1320 包含性通过；截图存在。人工记录独立绑定同一 JSON/HTML 哈希与实际查看截图。
- 检查当前 canonical/module Markdown 和生成 index.html 的本地链接；不扩展为清理历史文档。
- 检查根 `README.md` 的本地链接；触发代码/包清单改动时核对 README 复核回执是否进入变更集，
  并验证 `updated` 与 README 变更之间的条件关系。
- 对 README 门禁配置执行固定路径与固定触发集合校验，不能通过删项、加重复项或改指向缩小门禁。
- 对全部受跟踪 Markdown 执行状态分类；同一主题只允许一个 current 权威，当前文档的相对链接与锚点必须存在。
- 对当前文档拒绝已知退役命令；`docs/generated/py_file_index.md` 必须与生成器输出完全一致。
- 检查 docs-only、普通 Web、安装面、Windows、Tabbit 与 Desktop 的 workflow 路由；自动 workflow
  必须有 concurrency、取消旧运行和超时，Web artifact 保留期不得超过 3 天。Research Web 安装自动
  门只允许 GitHub macOS，Windows Web 与 Tabbit 暂停期间必须保持 `workflow_dispatch` 手动入口。

每个变化模块组在本次任务的 `.ai/reports/*.md` 中写入可机读标记，例如：

```html
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅增加只读设置入口，既有研究请求与文件预览边界保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"changed","reason":"新增离线一致性检查和隔离HTML入口，08图记录实际接线。","diagrams":["08-iteration-docs"]} -->
```

检查器只读取 changed-file 集内的任务报告；历史报告不会覆盖本次决定。同组最后一个标记生效；`changed` 必须列出组内实际变化的图源，`unchanged` 必须有具体原因。
文件和字符串匹配不能证明说明与箭头语义正确，人工源码/图文审查仍是独立交付条件。
自动回执的 `visualReview: pending` 不被检查器改写成伪造的人工通过。

## 只读 Web 入口

设置页固定链接 `/api/research/documentation/index.html`，用新页和
`rel="noopener noreferrer"` 隔离 opener；不自动触发模型或任何能力操作。
`app/research_web/documentation.py` 仅允许 index 与十张图的固定 HTML 文件名，根目录固定为
`outputs/research-web-architecture/`。不提供 Markdown、JSON 回执、截图、目录浏览或任意路径读取。
缺失/非法文件返回无路径泄漏的 `documentation_unavailable` 404。

目录逐级以 `O_NOFOLLOW` 打开，最终文件拒绝符号链接/硬链接并检查普通文件类型及 4 MiB 上限；
通过已打开描述符读取全部响应字节，避免先校验后按路径重开的竞争窗口。此路径使用 POSIX
文件描述符能力，未做 Windows/桌面支持声明。

只有成功的固定文档路由保留自己的 CSP：`sandbox allow-scripts`，无 `allow-same-origin`，
无网络连接、表单提交或 base URL 权限；只允许内联 viewer 脚本、样式与 data 图片。
原产品 `script-src 'self'` 与研究文件的空 sandbox 预览政策不变。图册的 opaque origin 会让
相对图页链接带 `Sec-Fetch-Site: cross-site`：中间件仅对固定十二个公开 HTML（入口、API Atlas 加十图）的 GET 请求提供
窄例外，且须同时满足 `Sec-Fetch-Mode: navigate`、`Sec-Fetch-Dest: document` 和
`Sec-Fetch-User: ?1`。跨站 fetch、iframe、非 GET、未知路径和研究 API 仍拒绝；不开放 CORS。
no-store、no-referrer、nosniff 仍由现有中间件执行。

## 测试与日志

API Atlas 由 `scripts/build_research_web_api_atlas.mjs` 从同一接口清单离线生成；只包含 Method、路径、领域和仓库相对源码，不访问运行服务或外网。`/mcp/` 路由单独归类为 `MCP Registry`，避免把只读 Registry 同步、目录浏览和 Publisher 外部交接混入普通能力目录。

`tests/javascript/research_web_architecture.test.mjs` 构造独立临时十图 fixture，验证有效输入，
源码无说明、未映射模块、失效接口/前缀、图源或 HTML 与旧回执、缺图、断链、丢失截图和
旧人工哈希等负向案例；同一行为测试还覆盖缺少 README 回执、`updated` 漏改 README、无效或
空白 `unchanged`、合法两种结论及根 README 断链。fixture 的文本图片不是实际视觉证据，不进入生成文档目录。
`tests/javascript/documentation_governance.test.mjs` 验证未分类文件、重复权威、断链、缺锚点与退役命令；
`tests/javascript/actions_quota_governance.test.mjs` 验证 Actions 路由、平台边界、并发、超时和证据保留；
`tests/scripts/test_generate_py_file_index.py` 验证生成结果的确定性与公开结构漂移；
`tests/research_web/test_doc_sync.py` 验证 Python 聚合入口和 Git 失败边界；
`tests/research_web/test_documentation.py` 验证路由、CSP、穿越、链接、缺失及离线访问。
`tests/javascript/research_web_tabbit_workflow.test.mjs` 由同一快速 Project Constraints CI 执行，
只验证耗时 Tabbit 双平台矩阵保持 `workflow_dispatch` 手动触发，不运行该矩阵本身。

架构与治理 CLI 将非敏感计数和错误代码分别写入 `logs/research-architecture-check.jsonl` 与
`logs/documentation-governance.jsonl`；
后端与 Python 入口使用项目日志设施，不记录请求输入、秘密或任意异常文件路径。
单元测试不能代替真实浏览器脚本交互、人工看图或模型/平台验收；这三类证据应分别记录。
