# Task 4 限定审查修复

工作树：`.worktrees/dsh-web-v1`；起点 `68e8775`。仅修复独立审查的五项 Important。
原实现记录保留在 `2026-09-03-research-documentation-gate.md`，本记录不改写旧失败或旧验收。

## 根因、RED 和修复

| 问题 | 编辑前复现 | 最小修复 |
| --- | --- | --- |
| 非对象 map 被判通过 | `null` / `false` / `0` / 空字符串使违规列表为空 | 顶层强制非 null 对象，invalid map 明确 `map_schema`；CLI 退出1 |
| sandbox 图册点击图页 403 | 控制器真实浏览器已发现 cross-site；新增带真实导航头的 TestClient 断言亦得403 | 仅固定九个公开文档路径的 GET + navigate + document + 用户激活 `?1` 允许跨站导航；研究 API/preview、未知路径、fetch、iframe、POST、HEAD仍403；CSP/CORS不变 |
| CI Git 失败被丢弃 | 实际 workflow shell 在无效base上仍执行下游checker并退出0；含换行文件名变成Git quoted string | `git diff -z` 写到受控临时文件，检查退出状态后再NUL解析；失败直接退出1，临时文件退出清理 |
| 关键字 API 漏登 | `@app.get(path=...)`、前置 summary/tags 和跨行 path 都未入清单 | 扫描所有受支持HTTP装饰器，括号/引号感知分隔参数，支持字面量位置/path关键字；动态/无法支持声明明确失败，不跳过 |
| 生成输出目录越界 | HTML/两类回执改为根前缀内的 `../outside` 或任意别名，旧检查仍通过 | 读取前比较规范化路径及按八图ID固定的HTML/receipt/visual-check文件名 |

新增Node回归21项：首轮19失败、2项已有合法防护通过；修复后含原30项共51通过。
新增Python导航例外回归9项：正向旧403明确RED；修复后文档模块23项通过。
负向场景保持不修改运行时状态，不请求真实模型/数据。

## 实际验证

Python解释器为已有当前macOS环境 `/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python`。

```text
node --test tests/javascript/research_web_architecture.test.mjs
  51 passed
<python> -m pytest tests/research_web/test_documentation.py --confcutdir=tests/research_web -q
  23 passed
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs
  122 passed, 0 failed, 0 skipped, 1.818s
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness <python> -m pytest tests/research_web --confcutdir=tests/research_web -q
  259 passed, 24.43s
<python> -m ruff check app/research_web/main.py tests/research_web/test_documentation.py
  passed
<python> -m black app/research_web/main.py tests/research_web/test_documentation.py --check
  2 files unchanged
<python> -m isort app/research_web/main.py tests/research_web/test_documentation.py --check-only
  passed
<python> -m mypy app/research_web/main.py --follow-imports=skip
  success; existing unused transformers configuration note only
node --check scripts/check_research_architecture.mjs
node --check tests/javascript/research_web_architecture.test.mjs
git diff --check
  passed
<python> scripts/check_task_completion.py
  passed（包含控制器当前文档变更，未将其纳入本次提交）
node scripts/check_research_architecture.mjs --project . --base 304930d
  violations: []
<python> scripts/check_doc_sync.py --project . --base 304930d
  violations: []; Documentation sync check passed
node --input-type=module -e "import {checkProjectConstraints} from './.agents/project-constraints.mjs';import {collectChangedFiles} from './scripts/check_research_architecture.mjs';const r=checkProjectConstraints({projectRoot:'.',changedFiles:collectChangedFiles('.','304930d')});console.log(JSON.stringify({count:r.checkedFiles.length,violations:r.violations}));process.exitCode=Number(r.violations.length>0)"
  count: 200; violations: []
```

后三项整轮检查消费控制器当前工作树中的八图、模块文档和真实人工回执；这些文件仍由控制器维护，未纳入本次提交。
CI shell失败/文件名回归实际提取并执行当前workflow的run块，仅下游checker使用fixture桩，未调用GitHub。

## 文件与未验证边界

自有改动：`scripts/check_research_architecture.mjs`、`.github/workflows/project-constraints.yml`、
`app/research_web/main.py`、两份最近Node/Python回归测试、`docs/research-web-documentation.md`、
`docs/modules/scripts.md` 与本报告。无新依赖、无live重启、无研究调用、无DSH/桌面改动。

控制器负责在其授权的空闲reload后重新运行真实 `tests/e2e/research_web_documentation.mjs`。
当前仅Header/TestClient模拟导航已GREEN，不称真实浏览器已通过；实际GitHub CI亦未运行。
最终Harness沿用原始主项目任务 `task-9dcfa3c8-ui-capabilities`，由控制器统一结算，未补造s4开始事件。
