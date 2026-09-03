# Task 4 — Research Web 文档一致性与安全入口

状态：实现完成，待控制器八图集成/真实浏览器/Harness 最终交付检查；不宣称整轮完成。
工作树 `.worktrees/dsh-web-v1`，分支 `codex/dsh-web-v1`，任务起点 `b7a99a3`。

## 变更—证据

| 源变更 | 测试 | 文档 | 实际结果 |
| --- | --- | --- | --- |
| `scripts/check_research_architecture.mjs` | `tests/javascript/research_web_architecture.test.mjs` | `docs/research-web-documentation.md` | 30 fixtures通过，包含源码/Markdown、API/挂载/前缀、图文哈希、链接、视觉回执与人工记录负向 |
| `scripts/check_doc_sync.py` / `.agents/project-constraints.{mjs,json}` / 现有 Project Constraints CI | 上述 Node + `tests/research_web/test_doc_sync.py` | `docs/modules/scripts.md` / 专属说明 | 两个入口使用同一Node core；Python三项通过，Git错误不视为空变化，失败不打印整体通过 |
| `app/research_web/documentation.py` / `main.py`挂载 | `tests/research_web/test_documentation.py` | 专属说明 | 14项通过：固定HTML白名单、逐级nofollow、硬链接/过大文件拒绝、404不泄漏、独立CSP |
| `app/research_web/ui/app.mjs` 设置入口 | Node设置测试 + 原有完整UI回归 | 专属说明；UI主文档由控制器更新 | 固定只读链接，noopener/noreferrer，不涉及研究控制器 |

## RED → GREEN

- 首次Node fixture运行25失败：仓库内核心不存在；实现后25/25通过。
- Python首先因新路由未挂载失败；修正测试对FastAPI路由集合的读取后，再次确认明确断言失败；实现后12/12通过。
- Python入口两个测试最初错误返回0；加入显式project/base/files委托后2/2通过。
- CI委托/设置链接两项最初失败，接线后27/27 Node通过。
- 未挂载API和重复人工截图两个负向最初无违规；实现后，加上前缀用例合计30/30 Node通过。
- 硬链接读取和错误后整体通过文案各出现真实失败；修复并增加过大文件测试后17项Python聚焦通过。

## 已执行命令

以下Python均使用当前macOS已有解释器 `/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python`，未安装依赖。

```text
node --test tests/javascript/research_web_architecture.test.mjs
  30 passed, 0 failed
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs
  98 passed, 0 skipped, 1.642s
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness <python> -m pytest tests/research_web --confcutdir=tests/research_web -q
  250 passed, 32.99s (完整末轮；此前247 passed/27.00s)
<python> -m pytest tests/research_web/test_documentation.py tests/research_web/test_doc_sync.py --confcutdir=tests/research_web -q
  17 passed, 1.41s
<python> -m ruff check app/research_web/documentation.py app/research_web/main.py scripts/check_doc_sync.py tests/research_web/test_documentation.py tests/research_web/test_doc_sync.py
  passed
<python> -m black app/research_web/documentation.py app/research_web/main.py scripts/check_doc_sync.py tests/research_web/test_documentation.py tests/research_web/test_doc_sync.py --check
  5 files unchanged
<python> -m isort app/research_web/documentation.py app/research_web/main.py scripts/check_doc_sync.py tests/research_web/test_documentation.py tests/research_web/test_doc_sync.py --check-only
  passed
<python> -m mypy app/research_web/documentation.py app/research_web/main.py scripts/check_doc_sync.py --follow-imports=skip
  Success: 3 files; existing unused transformers configuration note only
node --check scripts/check_research_architecture.mjs
node --check .agents/project-constraints.mjs
node --check app/research_web/ui/app.mjs
git diff --check
  passed
<python> scripts/check_task_completion.py
  passed（包括工作树中控制器正在维护的文档变更）
```

`node scripts/check_research_architecture.mjs --project . --base b7a99a3` 首次真实清单检查退出1，
仅六项预期集成缺口：UI说明未更新、UI/research-api核对标记缺失、新文档模块/API未登记、
第08图未交付。对整轮base304930d再次用同一核心检查191条真实变更时退出1，八项缺口仍是
markers/新模块API/缺08；七图的实际字节、9/9回执、四视口和人工记录没有报错。
控制器负责canonical Markdown/map/八图/截图与生成入口，未将fixtures成功代替实际全图通过。

Harness runtime `--verify` 为 `valid:true, drift:[]`。对控制器提供的
`task-9dcfa3c8-s4` 在本worktree执行 `harness-enforce.mjs` 返回1：
`missing task_started event`。已告知控制器核对真实session task-id；未补造历史事件。

## 未触及与待集成

- 无模型调用、无网络技能安装、无秘密/运行时配置修改、无live服务重启、无DSH/桌面修改、无推送。
- canonical架构目录、生成图册、根文档与其他E2E产物均由控制器所有；此次不暂存。
- 固定文档路由的真实浏览器“设置→图册→图页”导航、viewer交互与opaque-origin sec-fetch行为待控制器验收。
- POSIX安全打开路径没有Windows支持声明；本轮没有原生Windows CI或桌面变更。
- 真实Project Constraints GitHub CI未运行；本机执行同一core和fixture，不冒称远程CI。
- 独立Python/JS审查由控制器继续安排；总体八图门禁与Harness未满足前不得称整个任务已交付。
