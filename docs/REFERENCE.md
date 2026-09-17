# Research Workbench 参考入口

本页是现役参考资料的导航，不复制完整 CLI、路由、Python 符号或目录树。旧版 2982 行手册保存在 [历史参考手册](archive/legacy/reference-manual.md)，只能用于维护兼容平台。

## 当前 CLI

安装后的权威入口由 `pyproject.toml` 的 `rwb = research_workbench_entrypoint:main` 和 `app/cli/main.py` 注册：

```bash
./rwb --help
./rwb web --help
./rwb web doctor --json
```

Windows 使用 `rwb.cmd`。`web start|status|restart|stop|doctor|tabbit-status` 与 `migrate-research-data`、`migrate-report-projects` 属于当前入口；其他按需加载的命令在帮助中明确标记为历史兼容命令。

## Research Web API

- 当前接口入口：`http://127.0.0.1:8088/api/research/`。
- 人工语义合同：[接口清单](architecture/research-web/04-api.md)。
- 机器清单：`architecture/research-web/architecture-map.json` 的 `apis`。
- 浏览器 Atlas：设置 → 架构文档 → API Atlas，或 `/api/research/documentation/api-atlas.html`。

新增、删除或改名路由时必须同时更新源码、机器清单、接口文档和负向测试；不能手工维护另一份完整路由表。

## Research Web 专项参考

- [DataHub](research-web-datahub.md)
- [能力与版本](research-web-capabilities.md)
- [文件交付](research-web-delivery.md)
- [Tabbit](research-web-tabbit.md)
- [脚本沙箱](research-web-sandbox.md)
- [运行与用量](research-web-operations.md)
- [研究框架](architecture/research-web/08-research-frameworks.md)
- [统一集成协调器](architecture/research-web/09-integration-coordinator.md)

## 兼容平台

旧 `app/api`、`app/web`、数据库、Connector、Signal Lab 和报告系统仍有实际源码。维护这些区域时从 [Development Map](DEVELOPMENT_MAP.md) 找到对应 `docs/modules/`、`DATA_STORAGE.md` 或 [旧数据源入口](DATA_SOURCES.md)，不要把旧端口、命令或数据要求写回 Research Web 入门文档。

## 生成索引

[Python 文件索引](generated/py_file_index.md) 由 `scripts/generate_py_file_index.py` 生成，适合查找类、函数和导入；它不是架构说明，也不得手工编辑。
