# Research Web 文档门禁与安全入口

## 模块边界

`scripts/check_research_architecture.mjs` 是仓库内、仅使用 Node 标准库的离线检查核心。
`scripts/check_doc_sync.py` 与 `.agents/project-constraints.mjs` 调用相同核心；现有
`.github/workflows/project-constraints.yml` 先运行负向 fixtures，再检查真实变更和清单。
不要求开发机绝对目录、Archify 安装、模型服务或网络，不生成或篡改回执。

输入契约见 [当前架构契约](architecture/research-web/06-documentation-contract.md)，
清单见 [architecture-map.json](architecture/research-web/architecture-map.json)。
最终必须包含 01–08 八图，不能用部分完成状态跳过门禁。

## 本地命令

```bash
node --test tests/javascript/research_web_architecture.test.mjs
node scripts/check_research_architecture.mjs --project . --base <git-revision>
python scripts/check_doc_sync.py --project . --base <git-revision>
node .agents/project-constraints.mjs --project . --changed-file app/research_web/main.py
```

Node/Python 命令均接受重复的 `--changed-file`。没有显式文件列表时读取 Git staged、
unstaged 与逐文件 untracked；`--base` 还包括该 revision 到 HEAD 的变更。错误 Git
revision、仓库缺失、回执无效会失败，不能当作空变更通过。离线非 Git fixture 可使用
显式文件列表或 Node `checkResearchArchitecture({projectRoot, changedFiles})` 函数。
显式文件列表应完整覆盖任务，不是用来隐藏实际改动的豁免。

## 检查内容与核对标记

- 所有 Research Web Python、JS/MJS、CSS、HTML、Skill Markdown/脚本/模板与配置均检查映射。
- 映射的源码、模块 Markdown、测试、图节点和关系证据必须存在且不经过符号链接。
- 扫描源码中的 HTTP 装饰器及 APIRouter 前缀，双向比较接口 inventory；新增遗漏和旧接口均失败。
- 变更组的每份模块说明和本次 review-record 必须出现在变更清单；核对记录有明确结构决策。
- 图源、HTML 的实际 SHA-256 和字节数必须匹配 deliver；要求 showcase 9/9、零错误零警告。
- 视觉回执必须绑定当前 HTML，四个固定视口 1440×900 / 1600×1000 / 1920×1080 /
  2048×1320 包含性通过；截图存在。人工记录独立绑定同一 JSON/HTML 哈希与实际查看截图。
- 检查当前 canonical/module Markdown 和生成 index.html 的本地链接；不扩展为清理历史文档。

每个变化模块组在 review-record 追加可机读标记，例如：

```html
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅增加只读设置入口，既有研究请求与文件预览边界保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"changed","reason":"新增离线一致性检查和隔离HTML入口，08图记录实际接线。","diagrams":["08-iteration-docs"]} -->
```

同组最后一个标记生效；`changed` 必须列出组内实际变化的图源，`unchanged` 必须有具体原因。
文件和字符串匹配不能证明说明与箭头语义正确，人工源码/图文审查仍是独立交付条件。
自动回执的 `visualReview: pending` 不被检查器改写成伪造的人工通过。

## 只读 Web 入口

设置页固定链接 `/api/research/documentation/index.html`，用新页和
`rel="noopener noreferrer"` 隔离 opener；不自动触发模型或任何能力操作。
`app/research_web/documentation.py` 仅允许 index 与八张图的固定 HTML 文件名，根目录固定为
`outputs/research-web-architecture/`。不提供 Markdown、JSON 回执、截图、目录浏览或任意路径读取。
缺失/非法文件返回无路径泄漏的 `documentation_unavailable` 404。

目录逐级以 `O_NOFOLLOW` 打开，最终文件拒绝符号链接/硬链接并检查普通文件类型及 4 MiB 上限；
通过已打开描述符读取全部响应字节，避免先校验后按路径重开的竞争窗口。此路径使用 POSIX
文件描述符能力，未做 Windows/桌面支持声明。

只有成功的固定文档路由保留自己的 CSP：`sandbox allow-scripts`，无 `allow-same-origin`，
无网络连接、表单提交或 base URL 权限；只允许内联 viewer 脚本、样式与 data 图片。
原产品 `script-src 'self'` 与研究文件的空 sandbox 预览政策不变。回环 Origin/跨站请求检查、
no-store、no-referrer、nosniff 仍由现有中间件执行。

## 测试与日志

`tests/javascript/research_web_architecture.test.mjs` 构造独立临时八图 fixture，验证有效输入，
源码无说明、未映射模块、失效接口/前缀、图源或 HTML 与旧回执、缺图、断链、丢失截图和
旧人工哈希等负向案例；fixture 的文本图片不是实际视觉证据，不进入生成文档目录。
`tests/research_web/test_doc_sync.py` 验证 Python 委托和 Git 失败边界；
`tests/research_web/test_documentation.py` 验证路由、CSP、穿越、链接、缺失及离线访问。

Node CLI/Project Constraints 将非敏感计数和错误代码写入 `logs/research-architecture-check.jsonl`；
后端与 Python 入口使用项目日志设施，不记录请求输入、秘密或任意异常文件路径。
单元测试不能代替真实浏览器脚本交互、人工看图或模型/平台验收；这三类证据应分别记录。
