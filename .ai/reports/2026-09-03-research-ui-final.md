# Research Web UI / 能力中心 / 架构文档交付

## 范围与结果

分支 `codex/dsh-web-v1`，起点304930d，全部业务改动位于`.worktrees/dsh-web-v1`；不覆盖主工作区。不新增依赖、引擎、外部MCP、定时任务或桌面功能。

- FinGPT/Claw独立首页、深色主导航与顶栏、可折叠会话侧栏、活动/资料/文件面板、当前工作区、真实搜索/分类/slash/草稿和附件。
- Skill/Tool/Workflow统一能力中心。四内置Skill、两研究步骤模板；对话创建、表单、手动SKILL.md/ZIP、检查、发布、禁用、版本回滚/导出。工具只展示已登记权限，Workflow交由原生DSH执行。
- 包和版本由产品管理，DSH原生发现，活动任务阻止发布；包安全、依赖、原生兼容检查失败可见。没有全局扫描或静默安装。
- 当前架构唯一入口`docs/architecture/research-web/README.md`，八张JSON/HTML/哈希回执与视觉证据；本地与CI共用检查器。设置只公开固定9个HTML，不开放仓库或私有目录。
- 真实验收发现的停止终态缺失已增加保守复核；新事件竞态有RED→GREEN回归，旧失败记录保留，允许独立新请求继续。

## 实际验证

使用已有虚拟环境`python`。

| 实际命令或旅程 | 结果 |
|---|---|
| `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q` | 287 passed，34.15s，无skip |
| `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs` | 123 passed，2.95s，无skip |
| `python -m ruff check app/research_web tests/research_web` | 通过 |
| `python -m black app/research_web tests/research_web --check` | 46文件通过 |
| `python -m isort app/research_web tests/research_web --check-only` | 通过 |
| `python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip` | 26源码通过；未标注函数体默认未全量检查的提示保留 |
| `node --check app/research_web/ui/app.mjs`、`git diff --check` | 通过 |
| `node scripts/check_research_architecture.mjs --project . --base 304930d` | 无违反项 |
| `python scripts/check_doc_sync.py --project . --base 304930d`、`python scripts/check_task_completion.py` | 通过 |
| ProjectConstraints API使用collectChangedFiles(base304930d) | 全量本次变更，无违反项；曾误用API的base参数得到空输入，已纠正，不以空检查计通过 |
| 八图Archify deliver + visual-check | 每图9/9、0错误/警告；四视口、人工哈希核对 |
| 浏览器布局 | FinGPT/Claw/能力中心×1440/1600/1920/820/390，共15组通过 |
| 浏览器功能 | 对话创建→审查发布→调用→下载；手动导入→v2→停用→回滚v1；PDF、Workflow双Agent、停止与拒绝真实验收；最终只读回归通过 |

原始日志位于`logs/research-ui-final-*`及各E2E日志，浏览器回执/截图/下载位于`outputs/research-web-ui-acceptance/`。失败尝试及模型内容错误保留于[真实记录](2026-09-03-research-ui-live.md)。源代码独立复审和最终竞态复审均Approved；未声称远端CI执行。

源码→测试→文档→图对应关系见`docs/architecture/research-web/architecture-map.json`；本轮完整交付文件列表见`2026-09-03-research-ui-files.txt`。用户上传研报PDF仅保留在本地验收目录/会话，不提交进版本库；DOCX由现有忽略规则保留在本地及运行时，仍可正常下载。

## 可访问交付

- Web：http://127.0.0.1:8088/#/fingpt；能力中心：/#/skills。
- 实际自建Skill：验收·样本统计报告，1ba298cc4b754aee9496b7d1c5c78bf7 v1；研究7ee7b736-673a-4aff-8006-73de6c10b600，实际HTML文件3320abdf473d5e3d84d3df8f。
- 手动导入：528c5a3dd15849b0a7f29fbdf5441b01，当前启用v1，v2保留。
- Workflow研究：43170801-cfeb-4c89-914a-a6973dbb8c9a；v2 DOCX b7633244999e079045942b68、HTML 1ccf91d946c2a7da1bcf9aa7、XLSX 849f14dbac3a9be567fbaf93。可在会话文件面板下载，哈希见真实记录。
- 启动命令及当前架构：[主入口](../../docs/architecture/research-web/README.md)。运行中的8088与3081无需重复启动。

## 明确保留的限制

单人、本机、单Web worker；未验证远端CI、公网、多租户、Linux/Windows沙箱、桌面和屏幕阅读器。基金研究资料有基准/完整总回报等缺口，报告为受限评价，格式合格不保证观点或计算正确。DSH原生终止事件序列化异常未升级内核修复；产品通过明确停止复核安全保留失败并继续。旧UE探针不做系统重启。未新增远程安装、账号或数据权限。
