# 图文更新清单契约与门禁

项目约束现在额外要求 `.github/workflows/research-web-bootstrap.yml` 在原生 `macos-14`
持续执行干净安装、公开 setup 入口、Doctor、CJPY 0.5.2 和无凭据天软不可调用断言。
Windows Web 验证保留原生 `windows-2022` 任务，但暂停自动触发并只接受用户显式 `workflow_dispatch`；
未运行时不生成 Windows 通过结论。该 Web 平台路由与本文件的架构图/回执门禁并行，也不改变
Desktop/Tauri/sidecar 的独立 Windows 验收规则；这些门禁不能互相替代。

本文件定义实际 `scripts/check_research_architecture.mjs` 的输入格式；Python 文档检查与现有 Project Constraints CI 调用同一仓库内检查器。快速 CI 同时运行 Tabbit 手动触发契约测试，防止耗时双平台矩阵重新挂回普通 push 或 pull request，但不执行矩阵本身。详见 [门禁模块说明](../../research-web-documentation.md)。CI 配置已接线，未声称远端 CI 已执行。

Project Constraints 还运行 Actions 额度路由契约：docs-only 只进入 Ubuntu 门禁；普通 Research Web 进入 Linux 检查；安装、Windows、Tabbit 和 Desktop 分别使用独立且有界的触发面。额度与冻结状态以 [Actions 额度治理](../../actions-budget.md) 为准。

## 最小验收计划合同

`.agents/verification-policy.json` 是 changed-file 风险与验收门的唯一机器真源；`scripts/plan_verification.mjs` 只读校验策略和仓库相对路径，按最高风险合并多文件计划。公开契约、schema、依赖、CI、安全、桌面、发布和未知路径 fail-closed 到 `full-delivery`；普通 Research Web 路径不得附加桌面门。

`.claude/commands/verify-task.md` 只是 `package-internal` 的薄兼容入口，必须调用项目规划器并按 JSON 输出执行，不得复制规则表。规划器本身不运行测试、Git、CI 或发布；Project Constraints 与受管交付控制器分别验证项目硬门和真实交付状态。

## 根 README 复核回执

每次改动 `app/research_web/`、`app/cli/`、`research_workbench_entrypoint/`、`pyproject.toml`
或 `package.json`，变更文件列表必须包含
[`readme-review.json`](readme-review.json)。回执是仓库内普通 JSON 文件，且只能包含
`schemaVersion`、`disposition`、`summary`、`reason` 四个字段：版本固定为 `1`，结论只能是
`updated` 或 `unchanged`，摘要和原因必须是去除首尾空白后仍非空的文字。

`.agents/project-constraints.json` 中的 `readmeReview` 块是强制固定契约：`readme` 只能是
`README.md`，`receipt` 只能是上述回执路径，三个目录前缀和 `pyproject.toml` / `package.json`
必须与检查器内置集合完全相等。数组顺序不影响结果，但空数组、缺失、额外项、重复项或路径重定向
均在读取配置时关闭失败；检查器后续使用自己的固定值执行触发与 changed-file 判断。

本轮回执进入变更集且结论为 `updated` 时，`README.md` 也必须进入同一变更集；`unchanged`
则用具体原因证明根说明无需调整。回执本身始终接受 schema、普通文件、仓库内路径和无符号链接
校验。已提交的历史 `updated` 不要求未来无关迭代重复改 README。

## 清单文件

`architecture-map.json` 使用仓库相对路径，不依赖开发机上的 Archify 安装或绝对源码位置。

| 字段 | 用途 |
|---|---|
| `schemaVersion` | 当前为 1 |
| `canonicalEntry` / `reviewReceiptDirectory` | 当前架构主入口及任务级核对报告目录 |
| `artifactRoot` / `visualReview` | 唯一生成文档根目录、人工查看记录 |
| `groups[]` | `id`、`sources`（目录前缀或精确文件）、`documents`、`diagrams`、`tests` |
| `apis[]` | `method`、完整 `path`、实际 `source`、装饰器中的 `declaredPath` 及 `prefix` |
| `diagrams[]` | `id`、JSON `source`、HTML `artifact`、`receipt`、`visualReceipt`、`evidence` |
| `evidence[]` | 图中 `subjects`（节点或关系 ID）对应实际源码 `source`；可增加字符串 `contains` 定位具体声明 |

清单包含十图、各节点与关系的关联来源及实际 `/api/research/` 路由，不允许以空清单绕过检查。新增报告 Workflow 运行序列与 Excel 数据流也必须经过同一哈希、视觉和人工审阅门禁。API Atlas 对 `/mcp/` 使用独立 `MCP Registry` 分类，分类脚本改动同样需要文档组标记与重新生成的 Atlas。

## 更新检查规则

源码变更先匹配模块组。Python、JS/MJS、CSS、HTML、Skill 文档/模板/脚本和 Runtime 配置都必须被覆盖。相关模块说明与本次 `.ai/reports/*.md` 任务报告需要更新。检查器只读取 changed-file 集里的报告；结构未改变时说明“不改图的原因”，不强制为了凑 diff 改图坐标。

JSON 改动需要重新生成对应 HTML 和交付回执。检查实际字节的 SHA-256/长度是否与 Archify `deliver` 回执相符，回执必须报告 showcase 9/9、零错误零警告。视觉回执必须对应相同 HTML 哈希且四视口包含性成功，截图文件存在。人工记录另绑定相同哈希，并列出实际查看截图；不篡改自动回执里的 `visualReview: pending`。

接口检查核对声明源码、HTTP method、完整路径和路由前缀；不存在、过期或新接口漏入清单应失败。源码与测试引用必须存在并位于仓库；根 `README.md`、当前架构 Markdown 和生成入口的本地链接必须可解析。历史文档的全部遗留链接不扩充为此任务范围。

检查支持显式变更文件列表或 Git base，用于本地交付及现有 Project Constraints CI；CI 只运行仓库内检查器，无需生成图或调用全局 Archify。检查不会访问模型或上游金融数据。

## 必须提供的负向证据

- 仅改研究源码而未更新对应说明/核对记录。
- 仅改图源或 HTML，未同步相应回执。
- 清单引用不存在的 API、源码、测试或本地文档链接。
- 触发目录或包清单已变更，但变更集缺少 README 复核回执；或 `updated` 回执缺少根 README。
- 回执不是仓库内普通文件、包含额外字段、JSON 无效，或摘要/原因只有空白。
- 图示遗漏节点/关系的源码关联，或视觉记录仍绑定旧 HTML。
- 变化属于结构调整，但核对记录没有说明图文如何同步。
- Markdown 未被治理清单分类、主题存在重复 current 权威、当前链接/锚点失效或退役命令重新出现。
- Python 文件公开结构变化后，生成索引仍是旧内容。
- docs-only 触发原生平台、安装面没有触发 Bootstrap、普通 Web 缺少 Linux 检查、Tabbit 重新自动触发，或自动 workflow 缺少并发取消、超时和短期 artifact 保留。

一致性检查不是语义证明：人工仍需核对箭头、版本/权限边界、失败状态与真实代码。未通过的产品、模型或平台验收必须单列，不能被图文检查结果覆盖。

## 执行与变更标记

`node scripts/check_research_architecture.mjs --project . --base <git-revision>` 检查 base 到 HEAD、staged、unstaged 与 untracked。`python scripts/check_doc_sync.py --project . --base <git-revision>` 复用核心并保留原 Python 文档要求。参数错误、Git 失败或校验不完整均失败。

本次任务报告使用 `<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"具体说明为什么本次模块边界与状态未变，不能只写已更新。","diagrams":[]} -->`。结构变化使用 `changed` 并列出本次真实改动的对应图源 ID；结构未变无需制造图源变更，但仍提交任务级说明。

Web 只读入口 `/api/research/documentation/index.html`、由接口清单生成的 `api-atlas.html` 及十个固定图文件由 `documentation.py` 提供；逐级 nofollow、硬链接拒绝、4 MiB 限额与隔离 CSP，不提供仓库或 Runtime 私有路径。
