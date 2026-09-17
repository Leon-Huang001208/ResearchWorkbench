# 数据源文档入口

本页用于区分当前 Research Web DataHub 与旧 Connector／摄入平台，避免把“代码存在”“目录登记”或“历史可用”误写成当前可调用。

## 当前 Research Web

[Research Web DataHub](research-web-datahub.md) 是当前数据源合同的唯一权威说明。代码与测试当前固定：

- 15 项品牌无关业务能力。
- 22 个登记来源。
- 登记、配置、授权、探测、适配和当前可调用是六个不同事实。
- DataHub Broker 在每次调用时选择满足合同的 Provider；目录中出现来源不代表已经完成真实连接验收。
- 真实来源状态和已验证范围以 DataHub 文档及对应 `.ai/reports` 为准。

实现入口：

| 范围 | 源码 |
| --- | --- |
| 能力／来源静态目录 | `app/research_web/datahub/catalog.py` |
| Provider 与 Broker | `app/research_web/datahub/providers*.py`、`broker.py` |
| 配置与安全探测 | `app/research_web/datahub/connections.py`、`probes.py` |
| 五阶段集成状态 | `app/research_web/integrations/` |
| 会话不可变快照 | `app/research_web/datahub/snapshots.py` |

用户从 Research Web 的 Settings → Data Sources 配置和探测来源。不要用旧 `pip install`、环境变量示例或兼容 Connector 优先级替代当前设置页合同。

## 旧 Connector 与摄入平台

仓库仍保留 `connectors/`、`data_sources/`、`data_layer/`、`ingestion/` 和 `cron_jobs/`，供兼容 API、旧数据摄入和历史维护使用。完整旧手册位于 [Connector 数据源归档](archive/legacy/data-sources-connectors.md)。

维护旧平台时，以实际 `SourceSpec`、Connector 基类、适配器和模块测试为准；旧来源可运行也不会自动进入 Research Web DataHub。旧 PDF 转换、联网问答和 PostgreSQL 摄入合同分别以对应 `docs/modules/` 和 `DATA_STORAGE.md` 为准。

## 更新规则

- DataHub 能力、来源、Provider 或快照变化：更新 `research-web-datahub.md`、架构清单和对应测试。
- 旧 Connector 生命周期、SourceSpec 或采集器变化：更新对应 `docs/modules/`；只有用户可见兼容行为变化才更新本入口。
- 任何数量、支持状态或“已验证”结论必须来自代码、测试或真实探测证据，不能从历史 Changelog 推导。
