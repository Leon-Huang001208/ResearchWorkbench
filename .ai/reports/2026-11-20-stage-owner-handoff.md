# Stage 业主交接

Mac mini 管理工具增加 `owner-handoff`，用于业主明确接续未完成 stage 的场景。
默认只预览，应用须绑定审核原件、原账本、完整资源身份及预览摘要。
在现有 `rwb-docker` 操作锁内核对停止状态及卷引用，逐字归档并读回原账本后退休预留，
单独保存交接信息、原登记任务未知及业务 `INCOMPLETE`。原完成任务标记与 Docker 对象保留。

近处回归覆盖预览无写入、成功归档及保全、原件与计划漂移、运行中及共享卷拒绝、
重复应用和 CLI 参数绑定。实际测试、评审及 CI 结果随最终候选补录。
固定产品候选 `f6ec7bb22582564b626358a33936288e6fda70dc` 的 stage 部署另以现场回执验证。

Product-Progress: not-required — 本次仅新增管理员资源交接入口，研究产品界面与用户功能均无变化。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"沿既有Docker管理器与操作锁保存stage预留交接，没有新增服务、容器拓扑或业务数据流。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks步骤增加管理器回归并沿用Mac安装，未增加运行服务、验收执行器或平台交付节点。","diagrams":[]} -->

本地 Node 合同 258 项通过，文档治理、项目完整性、产品进展检查、shell 语法与 diff 空白检查通过。Docker 首批 20 项通过；镜像缺少 lsof 导致测试根收尾失败，正改用宿主收尾并保留原回执，后续批次另录。
