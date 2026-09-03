# Task 3 — 能力中心前端闭环

工作树：`.worktrees/dsh-web-v1`；分支 `codex/dsh-web-v1`；基线 `3f7963c`。

## 变更

- 新增 `capabilities.mjs`、`capability-editor.mjs`、`capability-controller.mjs`，分别负责目录/详情渲染、完整候选表单、真实生命周期请求。
- 首页、卡片、slash、下拉框与全局搜索共享 `/capabilities`；只读 Tool 来自 `/tools`，可选项只作为 `tool_ids` 放入草稿。
- 卡片展示中文名称/简介、分类、来源、状态、场景、输入和默认格式。内置只复制修改，自建可编辑、检查、发布、停用、启用、查看版本、回滚和导出。
- 导入 SKILL.md/ZIP 保留问题；编辑发送完整 DraftInput，不回传服务器问题字段。文本及二进制资源按原字节保留，脚本需显式确认当前哈希，修改文件会撤销审查确认。
- Workflow 有序步骤可添加、删除、上移/下移，关联 Skill 与 Tool；运行只投影收据中不可变版本的模板，实际活动独立显示。
- 对话创建仅准备专用会话与未发送草稿；明确发送后制作候选。审查入口只接受专用创建会话真实 outputs/SKILL.md 或 ZIP。
- 能力选择绑定具体版本并随草稿/幂等重试保留；显式输出格式（包括空数组）优先。运行时未就绪可浏览和编辑但禁止发送。
- 桌面导航显示文字；空首页无右侧空栏；桌面研究空间可折叠；手机有抽屉关闭按钮和全局搜索；slash Arrow/Enter/Escape 不提交模型。
- 修正控制器浏览器发现的活动摘要过期：SSE 回填摘要，能力中心重新读取列表，旧 running 缓存只提示而不永久禁止服务端校验操作。

## TDD 证据

1. `node --test tests/javascript/research_web_capabilities_ui.test.mjs`
   - RED：新增初始 11 项全失败；缺少 capability/editor 模块、API 与版本选择/创建会话方法，导航/格式契约不符。
   - GREEN：实现后 11/11；随后扩展最终 23/23。
2. `node --test --test-name-pattern='catalog cards|offline runtime' tests/javascript/research_web_capabilities_ui.test.mjs`
   - RED：2/2 失败，卡片无场景/输入，离线发送仍启用。
   - GREEN：2/2，通过目录元数据渲染和发送门禁。
3. `node --test --test-name-pattern='cached running|live session summaries' tests/javascript/research_web_capabilities_ui.test.mjs`
   - RED：2/2 失败，旧 running 缓存锁住发布、无摘要协调函数。
   - GREEN：2/2，真实快照回填和服务端最终裁决。
4. `node --test --test-name-pattern='publication adopts' tests/javascript/research_web_capabilities_ui.test.mjs`
   - RED：已成功发布 v3 后多余 GET 失败导致界面仍留 v2。
   - GREEN：采用真实发布完整响应，1/1。

## 验证范围

- 新增测试覆盖筛选/空态/禁用/错误、危险 HTML、版本和工具意图幂等、格式优先、导入依赖失败、活动冲突、重复发布互斥、候选持久化读取、二进制保留、脚本审查失效、仅真实创建产物可审查、固定导出 URL、真实 app 事件处理器的零模型/工具写入。
- 完整回归：`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`，最终 67/67 通过、0 fail / skip / todo；发现后续自审问题后重新完成最终回归。
- `node --check` 对 app/core/composer/shell/views/capabilities/capability-editor/capability-controller 八个修改模块逐一执行，全部 exit 0；`git diff --check` 通过。
- UI iteration 技能用于冻结已有选择器与状态边界；SDD 实现模板要求聚焦 RED/GREEN 和实现者自审，本任务未派生代理。

## 边界与未验证

- 未修改后端、依赖、运行时、模型、权限、桌面、CI、架构主入口或控制器 e2e/产物文件；未重启服务、未发模型请求或工具审批。
- 浏览器真实视口和模型/文件闭环由控制器执行；本报告不把本地 JS 或 DOM 边界测试称为真实视觉/模型验收。
- 已保存候选由后端持久化；未保存编辑仅保留本页内存。DSH 离线仍可通过 Web 后端读目录，但不提供 Web 服务完全离线的 PWA 缓存。
- 发布/目录切换的全局活动状态以服务端锁校验为准；目录声明不代表实际工具授权。
- 控制器报告本批 15 页面/视口初检通过，提交后仍由控制器重验。控制器真实创建链遇到后端历史文件账本读取已改名文件的问题，由其安排后端修复；本任务不修改后端，也不宣称该模型链已最终通过。
