# Research Web 文件交付检查子任务报告

## 范围与结论

隔离工作树：`/Users/leon/Desktop/Projects/AlphaFoundry/.worktrees/dsh-web-delivery`。
分支 `codex/dsh-web-delivery`，起点 `2fedf0c`。

已实现可选格式要求、基金评价等 Skill 默认值、哈希快照与幂等收据绑定、独立交付
状态、严格沙箱实际解析、历史恢复、单会话串行和前端呈现。重命名及原生问题改为
应用内表单。不将此子任务视为完整研究产品验收；真实模型与浏览器旅程由主集成
任务执行、单独取证。

未触及 runtime/、sandbox.py、3080、运行服务、秘密、依赖安装、旧数据库、桌面
和 Windows 打包。没有第二套研究数据库或自动补文件/重跑模型的编排循环。

## TDD 证据

- 新增首批 7 条 Python 用例后运行：7 failed，证实格式字段被忽略、详情无
  delivery、同键格式变化未拒绝。随后实现并得到 7 passed。
- 新增 4 条 JavaScript 用例后运行：4 failed，证实缺少交付呈现/选择持久化且
  仍使用 window.prompt。实现后 4 passed。
- 后续补全历史恢复、当前标记、活跃子 Agent、沙箱失败、换文件与链接、并发
  解析用例。新增“显式无需文件覆盖 Skill”及“执行已结束”措辞回归再次先失败，
  修复后全套通过。

## 变更—证据映射

| 源码 | 测试 | 文档 / 结果 |
| --- | --- | --- |
| delivery.py / delivery_validation.py | test_delivery.py | research-web-delivery.md；真实 macOS 沙箱生成/解析与坏文件回归 |
| main.py / service.py / store.py | test_api.py / test_store.py / test_delivery.py | research-web.md；格式契约、幂等、冷恢复、单会话任务边界 |
| ui/app.mjs / core.mjs / views.mjs / styles.css | research_web_delivery.test.mjs / research_web_ui.test.mjs | research-web-ui.md；真实模块渲染/状态测试；未冒充浏览器验证 |

## 实际运行命令及结果

以下 `python` 均为已存在的
`/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python`。

```sh
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q
node --test tests/javascript/research_web*.test.mjs
node --check app/research_web/ui/app.mjs
python -m ruff check app/research_web tests/research_web
python -m black app/research_web tests/research_web --check
python -m isort app/research_web tests/research_web --check-only
python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip
python -m mypy app/research_web/delivery.py app/research_web/delivery_validation.py --follow-imports=skip --check-untyped-defs
git diff --check
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
git diff --cached --check
```

结果：Python **55 passed in 9.53s**（其中 14 条交付用例）；JavaScript **23 passed**；
app.mjs 语法、ruff、black、isort 通过。mypy 默认范围 12 文件通过，新交付模块
额外启用 `--check-untyped-defs` 的 2 文件检查通过（仅原有未使用配置段提示）。
测试 stdout 保存在 `/tmp/af-delivery-pytest.log`；应用/沙箱事件继续使用已有日志设施。
`check_task_completion.py` 通过；`check_doc_sync.py` 退出 0，但 Research Web 尚未
命中旧映射（输出无对应同步规则），不能将其视为文档内容自动审查。暂存差异空白检查通过。

## 未验证项、限制与后续集成

- 主集成任务需 cherry-pick 后运行真实基金 DOCX/HTML/XLSX 旅程、文件下载/隔离
  预览及重命名/提问表单浏览器交互。此子任务没有操作任何运行服务。
- 格式选择必须使用 expected_formats 或 Skill 默认值；不猜测自然语言格式要求。
  校验只证明格式可打开且有内容，不检查财务正确性、引证质量或完整研究质量。
- 只有本次新路径/哈希变化可计入；相同内容重新写入保守地不计入。每会话最多
  100 个支持格式输出，单文件 16 MiB，继承原沙箱 15 秒和输出限额。
- 校验失败不降级到宿主解析，也不会刷新后偷偷重跑。未知受理找不到原生标记时
  继续阻止同会话新消息，需查看历史或另建会话。
- 仅验证本机原生 macOS；未执行 Linux/Windows、旧数据库全套测试或桌面 CI。
- Harness 沿用主任务上下文；最终产品门禁由主集成任务执行，子任务不写虚假的
  整体 completed/passed 结论。

## 完整文件清单

```text
app/research_web/delivery.py
app/research_web/delivery_validation.py
app/research_web/main.py
app/research_web/service.py
app/research_web/store.py
app/research_web/ui/app.mjs
app/research_web/ui/core.mjs
app/research_web/ui/styles.css
app/research_web/ui/views.mjs
tests/research_web/test_delivery.py
tests/javascript/research_web_delivery.test.mjs
docs/research-web-delivery.md
docs/research-web.md
docs/research-web-ui.md
docs/CHANGELOG.md
.ai/reports/2026-09-02-dsh-web-delivery.md
```

## 规格审查修复（同日后续提交）

主任务审查发现并要求两项最小修正：

1. 空 analysis 表加两行 sources URL 曾被误判为有效分析底稿。新增 6 个明确
   元数据表名参数回归，在真实严格沙箱内生成/解析并先得到 6 个失败；修复为
   排除文档列出的精确元数据表名后，要求非元数据表有表头及非空数据行。另有
   analysis 表头+数值 0 与 sources 共存的正向用例。未增加金融语义治理规则。
2. 原生问题的 multiSelect 缺省/false 原应单选。后端缺省/false 两个回归先失败，
   true 多选原行为通过；JS 两个渲染/收集回归先失败。修复为默认 radio、true
   checkbox，前后端拒绝单选多个 selected。service.answer 仅在既有完整答案
   检查后新增基数校验，不触及主任务的子 Agent owner/response 路由。

本轮命令同上，实际结果：完整 Python **65 passed in 11.48s**、JavaScript
**25 passed**；ruff、black、isort、app.mjs 语法、mypy 12 文件及新增模块
`--check-untyped-defs` 2 文件、差异空白检查通过。完整 Python 输出：
`/tmp/af-delivery-review-all.log`；初始失败输出：`/tmp/af-delivery-review-red.log`。
本轮仍未操作服务/密钥/主工作树，未执行真实模型或浏览器验收。Harness
`task-8825dc0e-dsh-web` 的最终 outcome 由主任务维护，未更改。

## 发布前文件复核修复（同日第三次提交）

最终审查确认：沙箱解析返回的 valid 仅属于其读取的字节，原先 BFF 在结果返回后
没有再次检查路径内容。新增真实 macOS 沙箱回归，确认解析本身成功后，分别清空、
同字节长度替换、删除候选文件；修复前 3 个用例全部错误地 completed，实际运行
得到 **3 failed**。修复仅在 `delivery.py` 发布状态前，用既有 `Store.open_file`
安全描述符重读已通过候选并核对字节数/SHA-256；不再解析、不扩大沙箱、不增加
服务/UI 变动。差异或读取失败将文件置为无效，重新计算 missing_formats，并以
incomplete 落盘；新增用例同时检查返回结果和持久化收据。

实际验证：`test_delivery.py` **27 passed in 3.78s**；完整 Research Web Python
**68 passed in 11.40s**，命令仍为前述 `DSH_SOURCE_ROOT=... python -m pytest
tests/research_web --confcutdir=tests/research_web -q`。改动文件的 ruff、black、
isort、delivery.py 的 mypy `--check-untyped-defs` 与差异空白检查均通过。
本次未重跑未改动的 JS；前轮 25 passed 不冒充本轮新增执行。
失败/通过日志分别为 `/tmp/af-delivery-publish-red.log`、
`/tmp/af-delivery-publish-green.log`、`/tmp/af-delivery-publish-all.log`。

这是发布时点复核，不是不可变文件归档；发布后的外部修改不在本补丁保证范围。
未操作主工作树、运行服务、凭据或主 Harness outcome。
