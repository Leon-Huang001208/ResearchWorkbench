深入研究此前没有装配原生 Todo，研究空间也无法从原生日志恢复计划。本次在现有研究 preset 注册固定 DSH Todo，guard 仅新增精确 `todo_write`；详情/SSE 的计划投影与研究空间沿用唯一 DSH 及已有正文、执行和文件交付边界。

计划按原生回合/写入 seq 全量替换，新回合清空；重复和分页日志可恢复。缺失历史不猜回合，坏数据显示错误，取消/失败不被 Todo 完成覆盖。不提供稳定 item ID，不把多个 in_progress 解释为并行执行，不用 Todo 替代文件交付验收。

验证：
- Python protocol/event_recovery/runtime_launch：180通过，0 skip；新增负向用例已保留 RED→GREEN。
- Node24 两组既有 JS 与新增用例：69通过，skip/todo均0；工具权限与48工具/4子任务预算不弱化。
- 固定 DSH 无模型真实插件集成：真实Loader、工具执行、两次 todo/write 耐久落盘/完整日志读取、合法turn/end后下一回合清空及 Web 投影恢复通过；另验证真实preset作用域、两个Agent隔离和无Todo作用域。
- 本地 L4 的9个门通过；另有6项真实浏览器渲染检查（原生日志投影及明确标注的协议样例），不是完整产品/模型live。
- 严格 mypy 导入闭包仍有14个白名单外错误；投影文件聚焦 mypy/ruff/black/isort通过，不把聚焦结果替代完整类型检查。

保持当前 DSH pin、依赖、安装器、Provider、数据库、CI和验收策略；用户明确授权补齐必要文档和生成物。当前只允许PR及自动通用/macOS CI；不merge、不dispatch Windows/Linux、不安装依赖、不调用付费模型、不操作生产runtime。Mac干净安装以本PR自动CI实际结果为准，未验层级保留NOT_RUN/BLOCKED。

证据与断点：`.ai/reports/fingpt-native-plan-v1/PROGRESS.md`、`REPORT.md`、`BLOCKED.md`；原始工具日志仅留本地。

集成证据纠正：初始无模型夹具未在下一turn前写turn/end，工具写入真实，但最后完整日志不可接受；旧收据已明确FAIL并保留拒绝证据。当前使用integration-valid-state与preset-integration-valid-state，两者经过原生SDK最终完整读取并通过。该修复只涉及测试报告/夹具，产品代码字节保持不变。初始候选c10cb6bf的三项CI均通过；修订候选仍以其新CI实际结果为准，不复用旧run冒充新候选通过。
