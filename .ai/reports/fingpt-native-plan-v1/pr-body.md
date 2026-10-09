深入研究此前没有装配原生 Todo，研究空间也无法从原生日志恢复计划。本次在现有研究 preset 注册固定 DSH Todo，guard 仅新增精确 `todo_write`；详情/SSE 的计划投影与研究空间沿用唯一 DSH 及已有正文、执行和文件交付边界。

计划按原生回合/写入 seq 全量替换，新回合清空；重复和分页日志可恢复。缺失历史不猜回合，坏数据显示错误，取消/失败不被 Todo 完成覆盖。不提供稳定 item ID，不把多个 in_progress 解释为并行执行，不用 Todo 替代文件交付验收。

验证：
- Python protocol/event_recovery/runtime_launch：180通过，0 skip；新增负向用例已保留 RED→GREEN。
- Node24 两组既有 JS 与新增用例：69通过，skip/todo均0；工具权限与48工具/4子任务预算不弱化。
- 固定 DSH 无模型真实插件集成：真实Loader、工具执行、两次 todo/write 耐久落盘/读取、下一回合清空及 Web 投影恢复通过。
- 本地 L4 的9个门通过；另有6项真实浏览器渲染检查（原生日志投影及明确标注的协议样例），不是完整产品/模型live。
- 严格 mypy 导入闭包仍有14个白名单外错误；投影文件聚焦 mypy/ruff/black/isort通过，不把聚焦结果替代完整类型检查。

保持当前 DSH pin、依赖、安装器、Provider、数据库、CI和验收策略；用户明确授权补齐必要文档和生成物。当前只允许PR及自动通用/macOS CI；不merge、不dispatch Windows/Linux、不安装依赖、不调用付费模型、不操作生产runtime。Mac干净安装以本PR自动CI实际结果为准，未验层级保留NOT_RUN/BLOCKED。

证据与断点：`.ai/reports/fingpt-native-plan-v1/PROGRESS.md`、`REPORT.md`、`BLOCKED.md`；原始工具日志仅留本地。
