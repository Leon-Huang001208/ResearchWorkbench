# 事件固定部署结构复核 · 2026-11-05

宿主为 macOS Mac mini；范围为 Web 功能部署准备及文档闭合，不是平台适配。此记录只认证维护 profile 的结构决定，不认证最终 CI、Mac bootstrap、实际常驻切换或业务接受。

## dual-runtime

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"apply-events只在既有macOS Native操作员增加封闭版本身份及事件日程证明，沿三锁、BirthFence、全账号保全恢复链；没有新增容器、运行节点或研究引擎，复核01-deployment与12-ai-news拓扑仍准确。","diagrams":["01-deployment","12-ai-news"]} -->

已阅读 `docs/architecture/research-web/diagrams/01-deployment.json` 与 `12-ai-news.json`。01 的 Native Web、Native DSH、RuntimePool、私网网关、产品根及独立 Docker 单元仍准确；新 `apply-events` 只约束既有维护过程，不产生新服务、端口或 Docker 操作。12 的 Host／共享网关、AIHOT API、worker、独立 PostgreSQL 及授权门不因事件部署变动。保持图源与产物原件，不宣称重画或重新完成视觉验收。

## private-multiuser

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"事件部署沿原网关通用/api/research/*代理、账号Host和唯一DSH；全账号索引增加@events保全与严格disabled证明，不增加租户路由许可、资讯队列或账号节点，复核01-deployment与12-ai-news拓扑保持。","diagrams":["01-deployment","12-ai-news"]} -->

事件 API 复用原通用 `/api/research/*` 代理，认证账号与后端选择不变；全账号业务索引及 `@events` 保全仍归既有私有数据根。严格 disabled 的事件源日程证明、Native 真实空列表、各 phase／恢复重验和 WAL／SHM／journal／孤儿标记拒绝是维护准入细化，不新增账号节点或资讯生产链。事件业务内部连接由既有图 14 承担，不能从本结构复核推定采集已启用或评分已取得生产资格。

## 固定身份与证据边界

前版固定 `db2ae9a48ceca365852072e622aa6627aa7d0b83`，事件功能固定 `a398a29429a1c0bdddd34ce50bc336fd6e20f2ee`，基础闭包为 `60416994f88eeead8a3891dbe9a7dfd617c566fc`。用户后来明确批准一并部署 `58ad352eeb925805ff00f46139a073fda15163d3` 新主线且 MCP 保持关闭，最终固定载荷为 `65a016b3525f0a395ee221bf44f1b208818b03e8` 关闭安全检查点。配置持久严格 false，并以实际 Facade 健康布尔确认；回滚还原原字段缺席。这些变化不新增运行节点，操作员资格与产品身份仍分别核验。采集保持 off，不使用 TRIAL 丢弃权限，不删除账号／历史，不修改 controller、自动白名单、依赖或固定 DSH，不启用真实模型调用。

最终候选原三项 CI、同候选 Mac 干净安装、真实切换与认证页面仍需各自证据。Docker 产品及 Windows／Linux 原生验收本轮未执行；原 integration 的 Constraints FAIL 作为历史证据保留，后续完整 changed-set 的文档校验结果单独保存在 `logs/doc-compliance/`，不得改写原失败。
