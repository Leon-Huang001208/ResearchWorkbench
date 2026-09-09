# Research Web 真实模型验收与功能收口

## 范围与结果

- 实施工作树：`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/dsh-web-v1`，分支 `codex/dsh-web-v1`，起点 `2fedf0c`。
- 已集成交付检查的三个提交 `b838d51`、`f288088`、`c5c45df`；本报告记录随后真实模型发现的问题与最终集成验收。
- 已通过本机真实 DSH 的多轮/刷新、PDF 引页、公开数据与图表/XLSX、双子 Agent 报告、基金 DOCX/HTML/XLSX、允许/拒绝/取消、后台子任务停止、模型失败恢复、断线恢复与重复提交旅程。
- [可访问地址、真实会话、下载文件和启动命令](../../docs/research-web-acceptance.md) 为交付入口；模型答案和文件来自实际执行，不使用演示或模拟结果替代。
- 不修改主工作树业务代码，不重启用户原有3080，不升级DSH、不读取/复制密钥、不安装依赖、不新增数据库、桌面或Windows改造。

## 变更与证据

| 变更 | 回归 / 真实证据 |
| --- | --- |
| 注册 `datahub_get_fund_data`，只接受CLS/基金查询参数，原生审批先于HTTP，请求/响应/重定向限制 | `research_web_public_data.test.mjs`；真实CLS三条、基金20条净值；原生审批允许、拒绝、取消日志 |
| 严格沙箱导入可信技能辅助脚本 | `test_sandbox.py`；真实PDF读取、两个子Agent分析、Office与PNG生成 |
| 子Agent交互按原生归属响应，父会话离线仍可停止后台子任务 | `test_event_recovery.py`；父已结束、子仍运行时Web停止，35秒后无结束产物 |
| 修复旧turn结束/新turn开始投影顺序、内部提交标记展示、真实时间和用量 | `test_protocol.py`、`test_delivery.py`、`research_web_ui.test.mjs`；刷新、重连和Claw活动面板浏览器检查 |
| 独立delivery状态、只计本次变化文件、Office有效内容、发布前哈希复核 | 交付子任务报告及 `test_delivery.py`；基金/行业Office真实重开和浏览器下载 |
| Skill流程明确父Agent审批取数，子Agent分析既有资料 | 四个原生Skill及模块文档；不改DSH原生子Agent approval=never策略 |

项目日志沿用已有logging与`logs/`；公开数据错误、审批拒绝、解析失败、越界访问均有明确结果，不吞错伪报成功。

## 先失败再修复

以下问题先添加失败回归再修改：可信脚本模块导入、数据源空白/十六进制数值与异常内容、turn开始事件、子Agent审批归属、父会话已卸载时取消、内部标记泄露/引用旧标记误裁剪，以及真实执行耗时显示。交付子任务另有损坏/缺失/旧产物、元数据表误判、单选多选、解析后文件变化的红绿证据，见同目录 `2026-09-02-dsh-web-delivery.md`。

公开数据、协议安全与交付由独立审查代理检查；最后发现的旧标记误裁剪已用最右内部标记修复，并测试两种标记顺序。未为了通过验收放宽沙箱或依赖固定输出。

## 实际回归命令

下列 `python` 为现有 `python`，工作目录为上述隔离工作树。

```bash
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs
python -m ruff check app/research_web tests/research_web
python -m black app/research_web tests/research_web --check
python -m isort app/research_web tests/research_web --check-only
python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip --check-untyped-defs
```

最终再次运行：Python **76 passed in 11.74s**，JavaScript **32 passed / 0 skipped**。
Ruff、Black（23文件）、isort通过；mypy 12源码文件通过（仅旧配置未使用段提示）。
前一轮同版本完整回归输出分别保存在 `logs/research-web-pytest-20260902.log`（76 passed / 11.57s）、`logs/research-web-js-20260902.log`；最终复跑输出另保留于任务执行记录。
真实模型和浏览器旅程独立记录于验收文档，不能从这些模拟协议单测推导。

## 已验证边界与未验证项

- 真实模型有效、原生日志恢复、当前产物可打开/下载/隔离预览。格式检查不保证研究观点正确；基金20条净值是数据源本次返回，报告明确缺少复权、基准、持仓、费率等，不冒充完整基金尽调。
- 当前只验证单人macOS本机Web和严格原生沙箱；未验证Windows/Linux部署、桌面安装、多人权限或任意MCP。没有声称这些已实现。
- 图片上传有回归，未做真实视觉识别；提供方所有中途断流变体未逐一制造。实际测试了真实无效模型失败和BFF断线。
- 原生子Agent审批策略为never，需要审批的取数由父Agent执行。这是当前DSH边界，不再建设第二套编排或越过拒绝。
- 早期沙箱探针PID38291仍是内核UE状态，只读复查并保留目录，未重启系统。当前父/子脚本停止已有独立成功证据。
- 本轮主工作树及其他会话不受改动；测试数据、真实验收会话与生成文件保留供用户直接查看。

## 最终门禁

已运行以下补充命令：

```bash
for skill in company-research document-reading fund-evaluation industry-research; do python -m mypy "app/research_web/skills/$skill/scripts/workflow.py" --follow-imports=skip --check-untyped-defs || exit; done
for module in app/research_web/runtime/*.mjs app/research_web/ui/*.mjs; do node --check "$module" || exit; done
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
git diff --check
```

四个独立Skill脚本类型检查、全部runtime/UI模块JS语法、任务完整性与差异空白检查通过。
文档同步命令退出0，但旧规则不包含research_web，因此不将此称为自动文档覆盖审查；本轮手工同步了模块文档、Skill说明、CHANGELOG和本报告。
最后只读查询runtime仍connected=true、owned_runtime=true、deepseek-v4-flash；真实浏览器仍展示原双Agent报告及文件，已保留交付标签。
