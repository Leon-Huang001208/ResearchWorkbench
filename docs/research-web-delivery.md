# Research Web 文件交付检查

## 契约与状态

`POST /api/research/sessions/{sid}/messages` 接受可选 `expected_formats`，仅允许
`md`、`html`、`docx`、`xlsx`、`png`，最多五项。显式数组优先于 Skill 默认值，
`[]` 表示无需文件，省略或 `null` 使用默认值。基金评价、公司研究和行业研究默认
DOCX / HTML / XLSX；资料解读和无 Skill 聊天默认不要求文件。自然语言里的格式
要求不会由确定性检查器猜测；应在界面勾选相应格式。

详情新增 `delivery`，与 DSH 的 `status` 分开；历史页面重新打开会话或 Web 重启后
仍读取同一幂等收据。`delivery` 包含 `task_id`、`required_formats`、实际候选 `files`
（文件 ID、SHA-256、大小、类型、有效性及原因）、`missing_formats`、`reasons` 和
最终检查时间。不复制聊天正文、研究结论或模型事实至产品索引。

| delivery.status | 含义 |
| --- | --- |
| pending | 已受理，等待对应原生回合和子 Agent 全部结束 |
| admission_unknown | 受理未知，等待原生历史确认，绝不重发 |
| completed | 所有要求格式均找到本任务新建/更新且通过解析的文件 |
| incomplete | 要求格式缺失，或仅有损坏/空内容文件 |
| verification_failed | 严格沙箱不可用、限额超出或检查结果不完整 |
| not_required | 本任务没有要求文件，未执行文件解析 |

`completed` 只证明文件格式/非空检查，不证明研究结论、数据、引用或财务计算正确。
DSH 的 `completed` 在 UI 显示“执行已结束”，不表示文件已经交付。

## 任务归属与幂等

1. 新请求在受理前对 `outputs/` 支持格式的文件做安全 descriptor 读取和 SHA-256
   快照。文件清单仅存元数据；宿主不调用 Office、HTML 或图像解析器。
2. 快照、格式要求、任务标记和幂等收据原子写入既有 `index.json`；原生 prompt
   含唯一 `[AF_TASK:…]` 标记和文件交付要求。
3. 校验器必须在原生 `user/message` 中找到当前标记，并找到其后的 `turn/end`，
   且父会话、子 Agent 均不再运行且双事件通道可用，才检查本任务产物。
4. 只接受新路径或相同路径但哈希已变的 `outputs/` 文件。`inputs/`、隐藏文件、
   符号链接、硬链接、历史未变文件均不满足要求。相同字节重新写入也保守地视为未变。
5. 父/子任务或交付检查未结束时拒绝同会话新消息，防止排队任务共享目录造成归属
   混淆；同一幂等键的已接受请求仍直接返回收据，改变格式/正文会被拒绝。
6. 未知受理只读取历史；精确标记及结束事件可恢复为已接受，不重发模型请求。
   找不到当前任务标记时保持未知/等待状态；可新建独立会话，但不猜测旧任务结果。
7. 最终结果冻结在该收据中，不因随后新任务产生同名文件而回填旧任务成功。每次
   新任务使用新的快照；旧收据不会成为新任务的有效输出证据。

单 Web worker 的约束保持不变。这不是第二套研究执行器，没有自动补文件/重跑模型循环。

## 严格沙箱解析

`delivery.py` 调用现有 `sandbox.run_script`，执行可信 `delivery_validation.py`
源文本。解释器默认 Web 进程当前 `sys.executable`，部署可在构建
`ResearchService(..., delivery_python=Path(...))` 时传入可信解释器。解释器、
Session 和所有限制仍由原 `SandboxConfig` / Seatbelt 验证；没有裸进程回退、
新网络权限、宿主项目读取或 `.pth` 启动执行。

沙箱中重新以不跟随链接的目录 descriptor 打开 `outputs/` 文件，读取后再次核对
快照哈希，并基于同一份不可变字节解析，避免检查期间换文件造成误判：

- DOCX：`python-docx` 实际重开，要求段落或表格有文本。
- XLSX：`openpyxl` 只读、`data_only=True` 重开，要求至少一张表有两行非空内容
  （表头与数据）；0 / False 是有效值，纯空表、仅表头、无缓存值公式不算有效数据。
- HTML：标准库 `HTMLParser` 解析 UTF-8，要求排除 head/script/style 后的可见文本。
- Markdown：UTF-8 非空文本。
- PNG：Pillow 实际打开并 `verify()`，要求 PNG 类型及正尺寸。

沿用 15 秒执行时限和 64 KiB 输出上限，单文件检查上限 16 MiB、每会话最多
100 个支持格式输出。超限/无法读取/解析失败返回明确非成功状态，不扩大权限。
解析器错误只输出固定异常类型与状态；宿主日志通过已有日志设施写入 `logs/`，
不记录文档正文或异常原文。当前仅原生 macOS 可执行，未验证 Windows/Linux。
继承原沙箱无总内存/总磁盘硬配额的限制，不适用于不可信多租户。

## UI

编辑器提供按 Skill 默认、显式格式勾选和“仅聊天，无需文件”。格式选择随草稿和
幂等请求保存；会话运行时可准备草稿，但不再排队发送。右侧独立交付区域展示格式
要求、真实文件、缺失/损坏原因；下载和预览沿用原同源文件端点与空 `sandbox`
iframe，不在宿主或顶层 DOM 渲染模型 HTML。

重命名与原生 questions 使用应用内表单，不依赖嵌入浏览器不支持的 `window.prompt`。
输入草稿在 SSE 重渲染时保留，提交失败仍可编辑；questions 保持原 `answers` 契约。

## 验证入口

使用已安装环境，不安装新依赖：

```sh
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q
node --test tests/javascript/research_web*.test.mjs
python -m ruff check app/research_web tests/research_web
python -m black app/research_web tests/research_web --check
python -m isort app/research_web tests/research_web --check-only
python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip
```

模型实际生成质量、浏览器完整旅程、外部检索和产品级验收由主集成任务另行记录；
此模块回归不冒充真实研究任务成功。
