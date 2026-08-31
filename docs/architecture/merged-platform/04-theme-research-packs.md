# 04 主题 Research Pack

## 职责

Research Pack 是声明式主题数据包：Manifest 固定声明主题边界、产业链、dataset schema、KPI 单位/频率/来源优先级/新鲜度、事件、资产暴露、研究模板和兼容版本。Pack 统一写入 `theme_observation`，再提供六类查询投影；不自建表、不携带网络或数据库权限。

首批 Pack 为黄金、航天、光伏、AI 基础设施。它们迁移 LSH 的数据资产和严格口径，不迁移策略、评分、订单、`score_hint` 或 `driver-summary`。

## 数据归属

- `theme_pack` 拥有 manifest 版本、内容哈希、生命周期、校验结果和启用状态。
- `theme_observation` 是唯一主题事实表，保存 `pack_key`、dataset/row identity、subject_ref、metric、typed value、unit、observed_at、available_at、source_ref、freshness、source_hash 和 typed payload。
- 六类首版读模型为 `snapshot`、`kpis`、`value-chain`、`events`、`assets`、`health`；都是查询投影，不新增物化表。
- 资产详情继续归现有 stock/index/etf/fund 事实；Pack 只保存 `AssetRef` 暴露关系。

## 禁止依赖

- manifest 插件权限仅 `normalize|validate|derive`；禁止 network/database/shell/任意文件写。
- Pack 不导入其他 Pack 的 repository，不拥有 Scheduler 或 Runtime。
- `derive` 必须引用输入 observation 和公式版本，不把模型生成数值写成事实。
- LSH CSV 中带 `score_hint` 的 catalysts 整文件不迁；`driver-summary.csv` 不迁；策略 YAML、纸面订单和评分表不迁。
- 社交/二手来源只能作为待验证事件线索，不能提升为 official/fresh。

## 公共 API 与类型

| API | 返回 |
|---|---|
| `GET /api/themes` | Pack catalog、version、status、boundary |
| `GET /api/themes/{key}/snapshot` | 最新事实快照、coverage 与 freshness |
| `GET /api/themes/{key}/kpis` | 类型化 KPI、单位、频率、来源、时间 |
| `GET /api/themes/{key}/value-chain` | 节点/关系及其证据引用 |
| `GET /api/themes/{key}/events` | 事实事件与待验证线索分层 |
| `GET /api/themes/{key}/assets` | AssetRef 暴露与依据，不复制资产事实 |
| `GET /api/themes/{key}/health` | dataset coverage、age、quarantine/rejected 统计 |
| `POST /api/themes/{key}/research-workspaces` | 生成预填研究请求，不直接生成结论 |

公共类型包括 `ThemePackManifest`、`ThemeObservation`、`ThemeSnapshot`、`DatasetManifest`、`KPIDefinition`、`ValueChainNode`、`ThemeAssetExposure`、`PackHealth`。`KPI Series`、`Value Chain`、`Related Assets`、`Events`、`Data Health` 是类型化读模型而非新的事实类型；所有值经 `ObservationEnvelope` 保留来源与时间。

## 主流程

1. Registry 读取 manifest，验证 key/version/kind、兼容版本、schema、KPI、来源优先级、freshness、事件声明和插件权限。
2. 迁移器默认 dry-run，逐文件计算 source hash，逐行解析 identity、时间、值、单位、来源和状态。
3. 通过行写入 `theme_observation`；缺失/冲突进 quarantine，非法或禁止字段进 rejected；重复 `source_hash + row_identity` 幂等跳过。
4. Repository 以查询组合六类投影；health 暴露覆盖和 age。
5. 用户从主题页显式创建预填 Workspace/Run，研究层只读取 observation。

首批数据边界：

- 黄金：价格、供需、ETF 持仓/流量、现货、SGE、央行储备和宏观指标。
- 航天：发射活动、产业驱动、主机厂映射、CN5082 估值/行情、ETF 份额/资金、成分基本面。
- 光伏：产业链周度价格/明细、价格交叉验证、装机/出口、供给盈利、估值情绪和行情；带评分暗示的 catalysts 不迁。
- AI 基础设施：模型目录/使用量、供应链营收、光模块海关、AI track、宏观/估值/行情事实；创业板 50 仅作为相关资产/市场代理，不继承其策略范围。

## 状态与失败

Pack 状态为 `discovered → validated → enabled → degraded|disabled`。manifest 失败停在 discovered 并记录校验结果；必要 dataset stale/unavailable 由 enabled 进入 degraded，来源恢复后回到 enabled；disabled 只读保留 manifest 版本和 observation。导入状态为 `scanned → accepted|quarantined|rejected|duplicate`，apply 只处理 accepted。来源恢复后写新 observation，不覆盖历史。

## 可观测性

日志字段包括 `pack_key/version`、`dataset_key`、`source_hash`、`row_identity_hash`、`outcome`、`freshness_status` 和安全错误码。指标覆盖 manifest validation、accepted/quarantined/rejected/duplicate、dataset age、projection latency、coverage 和 forbidden permission 拒绝。

## 测试与验收

- Registry 测试拒绝 network/database 等权限，验证 KPI 单位/频率/来源与 Pack 状态转换。
- 迁移测试覆盖默认 dry-run、重复哈希幂等、时间/单位/来源缺失、冲突和 quarantine 报告。
- 明确断言不迁 `score_hint`、`driver-summary`、策略 YAML、订单和评分。
- API 测试覆盖六类查询投影，确认未新增六张物化表。
- 黄金纵切验证七类数据；航天/光伏/AI 逐文件校验真实 LSH header 与来源语义。
- 研究预填测试确认只创建 Workspace/Run 请求，不写 `theme_observation`。
