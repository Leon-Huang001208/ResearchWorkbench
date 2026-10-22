# 全市场常驻部署

宿主 macOS Mac mini；任务 market-resident-deploy-20261022，操作员功能与常驻部署。用户已授权保留现有会话、数据、模型配置后部署及真实认证验收。Windows/Linux 原生和 Docker 产品验收交接 NOT_RUN。

## 固定合同

reviewed-market-overview-v1 / apply-market 固定旧版4d2e3c408663b64be9e58b03213f4ca8f1152733与产品PR179 merge5de7e5f2db95b8b501905af9cfdc30e8fe84db0b。旧 profile、version4事务、控制器/证据读取器及严格保全保持。无新增依赖或安装配置；核对 requirements/web.in、web.lock、setup_web.py、安装文档和原 Bootstrap。

## 本机回归

新增固定身份与 CLI 测试先失败（2 failed,6 passed），实现后完整操作员矩阵568 passed/29.59秒。五种产品 profile 均覆盖真实Git范围、文件模式/删除/回退/未知差异、CLI、journal恢复、全账号索引保全与失败事务。日志保留 logs/market-resident-deploy/；后续独立评审、CI、实际部署和认证页面证据分别记录，未完成前不声称通过。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"只增加固定旧4d2e及已合并全市场产品5de7的封闭部署身份，复用原事务；无新节点、HTTP、依赖或数据流，现有图准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原用户隔离、业务索引冻结、模型及会话保全合同不变；真实认证验收另证，不新增权限或拓扑。","diagrams":[]} -->
