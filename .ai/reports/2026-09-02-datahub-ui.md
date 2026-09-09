# DataHub Research Web UI — Task 2

## 范围

- 工作树：`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/dsh-web-v1`
- 分支：`codex/dsh-web-v1`
- 基线：`364c0bc2201c545bb09276202e11b79b05fd11c3`
- 仅修改 Research Web UI、对应 JS 测试与 UI 文档；未修改 DataHub 后端、运行时、全局 UI 或桌面端。

## 实现

- 右侧研究空间在“文件交付检查”和“运行活动”之间渲染独立的“研究资料”分区，仅消费 `service.detail.datasets`/SSE 快照，不新增 API 读取或轮询。
- 资料卡展示来源安全链接、状态、请求/实际日期范围、行数、分页语义、已抓取页/供应商总量、取数时间、`as_of`、缺失、限制、缓存复用和可用文件 SHA256。
- `partial` 即使分页结束也保持错误级警示；`snapshot` 明确为非完整历史；未知状态不显示为成功。空数组不展示虚构卡片。
- CSV、JSON、manifest 下载只由当前 `sid`、当前资料 `did` 和三个固定文件名构造；拒绝路径分隔符、编码分隔符、查询串、片段、任意文件名和返回数据中的外站 URL。下载辅助技术名称包含资料名称和文件格式。

## TDD 证据

- RED：`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web_ui.test.mjs` 在新增资料渲染/固定下载测试后为 **18 passed, 2 failed**；失败原因是 `renderDatasets` 和 `datasetFileURL` 尚未实现。
- GREEN（定向）：同一命令为 **20 passed, 0 failed**。

## 已执行验证

- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`：**34 passed, 0 failed, 0 skipped**。
- `node --check app/research_web/ui/app.mjs`：通过。
- `node --check app/research_web/ui/views.mjs`：通过。
- `git diff --check`：通过。

## 未验证项与风险

- 未启动服务、未调用真实来源或模型、未读取凭据，符合本 Task 边界。
- 未进行真实浏览器、键盘/屏幕阅读器或移动端视觉验收；由主代理负责集成验收。
- 前端路径检查是纵深防御，后端仍是会话/文件授权和文件完整性的权威边界。
