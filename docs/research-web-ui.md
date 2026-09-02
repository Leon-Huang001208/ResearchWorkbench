# Research Web 前端

## 范围与入口

`app/research_web/ui/` 是独立的 Research Web 正式应用源码，由 Research Web FastAPI 服务提供 `/` 和 `/static/`。不加载原 `app/web` 管线或原型脚本，不依赖前端构建工具，不新增第三方包。2026-09-02 真实模型与浏览器旅程见 [验收记录](research-web-acceptance.md)。

页面使用 hash 路由：`#/fingpt`、`#/claw`、`#/history`、`#/skills`、`#/settings`。会话地址形如 `#/fingpt?session=<encoded-id>`，刷新页面会重新读取该会话。

视觉延续已批准原型的深蓝顶栏、浅色研究画布、蓝色操作按钮、左侧导航和右侧研究空间；品牌图标复用现有本地资产。原型中的示例消息、进度、市场模块、Claim/Evidence/Quality Gate 与旧管线没有迁入。

## 模块

| 文件 | 职责 |
| --- | --- |
| `index.html` | 自托管资源入口、中文语言标识和键盘跳转入口 |
| `styles.css` | 桌面三栏、平板研究抽屉、手机导航、焦点/禁用/错误/减少动态效果状态 |
| `core.mjs` | `/api/research` API、SSE 生命周期、路由、草稿、幂等请求和会话竞态防护 |
| `markdown.mjs` | 安全文本转义、URL 白名单、有限 Markdown 子集 |
| `views.mjs` | 会话、审批、问题、活动、Agent、文件、历史与模型选项的渲染 |
| `app.mjs` | 页面组合和真实用户交互；配置秘密不进入持久浏览器存储 |

## 接口与行为

所有请求仅访问同源 `/api/research`；读取运行时、模型目录、工作空间、历史与 Skills 后展示真实响应。错误可见，不生成本地演示结果。目录部分加载失败会独立报告并保留上次成功结果。

- 新研究先 `POST /sessions`，再对新会话 `POST /messages`；消息带 `Idempotency-Key`。同一个失败草稿重试复用相同键；收到 `accepted: true` 才清空原稿。界面不伪造用户/助手消息或进度。
- 会话详情来自 `GET /sessions/{id}`；SSE `snapshot` 替换真实详情，`runtime_error` 显示运行错误。事件连接恢复只重新读取快照，不重发消息。跨会话旧响应会被忽略；较旧 HTTP 快照不会覆盖后来到达的 SSE 输出。
- 历史打开、重命名、取消、批准/拒绝均调用对应真实接口。运行时提问通过问题响应接口回复；根回合结束但子 Agent 仍活跃时保留运行状态和停止入口。
- Agent 卡片显示实际 tokens、错误、已结束回合累计耗时及历史截断提示；活动使用原生工具时戳显示耗时，并以 Agent 名称关联。无测量值不伪造数字。聊天隐藏本次内部任务后缀，但保留用户引用的旧标记和正文。
- 重命名和原生问题使用应用内表单；不调用 `window.prompt`。SSE 重渲染保留当前表单草稿；问题可选择选项并补充文本，仍提交既有原生 `answers` 契约。
  - `multiSelect` 缺省/false 为单选 radio，true 为多选 checkbox；前端收集与后端均拒绝单选多值。
- 编辑器提供显式 `expected_formats` 与按 Skill 默认格式；选择随草稿/幂等请求保存。父/子任务和交付检查未结束时不排队新消息，允许先准备草稿。右侧单独展示 `delivery` 的要求、实际文件、缺失/损坏原因；“执行已结束”不等于“文件交付已检查”。详见 [交付契约](research-web-delivery.md)。
- 升级调用 `POST /sessions/{id}/upgrade`，使用返回的新会话和 `draft`；草稿放入新编辑器，不自动提交。
- 附件使用 multipart `files` 字段上传；返回 ID 作为 `attachment_ids` 提交。上传成功仅代表后端收到了文件，不代表模型已读取或工具沙箱已执行。
- 文件下载只使用真实返回且经过检查的同源会话文件 URL。HTML 预览 iframe 使用空 `sandbox` 和 `no-referrer`，前端拒绝外部或任意路径的预览地址；后端仍负责授权、路径隔离和响应 CSP。
- 模型切换和配置调用 `PUT /runtime/model`。API Key 为密码输入，不回填，不写 localStorage/sessionStorage，不进入日志；提交时清空输入框。失败后如需更新 Key，用户需重新输入。
- 前端安全 console 事件只包含固定事件名、请求 method 和 HTTP status；不记录 URL、会话 ID、输入、文件名、响应正文或凭据。服务端持久日志由 Research Web 后端负责写入项目日志设施。

## Markdown 与安全边界

支持标题、段落、粗体/斜体、行内代码、围栏代码块、列表、引用、简单表格与 HTTP(S) 来源链接。原始 HTML 始终转义；不执行模型输出的脚本或 HTML，不远程加载 Markdown 图片。来源链接拒绝活动协议、凭据 URL、控制字符与协议相对 URL。不是完整 CommonMark 实现。

文件链接限定 `/api/research/sessions/{sid}/files/{fid}/download` 或 `/preview` 路径；拒绝路径穿越及编码分隔符。前端校验不替代服务器授权。

## 验证与限制

```bash
node --test tests/javascript/research_web_ui.test.mjs
node --check app/research_web/ui/app.mjs
git diff --check
```

独立 JS 测试涵盖真实解析/渲染、恶意 HTML/URL、API 结构化错误、multipart 上传、日志秘密隔离、幂等重试、跨会话竞态、SSE 重连/清理、Claw 升级草稿与文件 sandbox。

浏览器视觉、键盘/移动端状态和真实 DSH 全链路由集成任务另行验证。DSH 模型凭据、工具沙箱、文件读取与 Agent 执行能力取决于实际后端，不由 UI 模拟。此变更不涉及桌面安装或 Windows 运行验证。
