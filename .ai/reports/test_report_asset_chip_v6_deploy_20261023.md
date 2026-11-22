# 资产v6固定部署配置验收

macOS Mac mini，Web功能交付。任务`asset-chip-v6-deploy-20261023`。

产品精确绑定PR197合并eac6806822294d75da990c751d88ec156a417f62；现场旧版c1a260fa1d8dcf013426aca938d7e46a98aaee28、active=false、maintenance=false。v6增加封闭模式，不修改旧pin/控制器/兼容白名单。

严格ZIP读取器及其回归从Git提交ef27f643的两文件补丁复用，不沿用PR192过时产品pin。读取器从22d8修复至5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb，仅由v6接受；旧evidence哈希ec022e39保持。完整流、成员/CRC、真实checkout/tree、失败/过期结果仍拒绝。独立评审复现多job缺checkout借用其他job通过；新增四例，红测复现missing未拒绝，逐job非空唯一检查后4 PASS；其后完整闭包另存日志。

已执行`python -m pytest tests/research_web/test_model_provider_upgrade.py tests/research_web/test_resident.py tests/research_web/test_gateway_upgrade.py --confcutdir=tests/research_web -q`：1183 PASS、73.64秒，既有Starlette弃用提示1条。真实解释器及现存pytest路径在logs/asset-v6记录；未安装依赖、调用模型或供应商。完整Router、独立评审、最终三CI/macOS安装、合并和真实部署分别绑定最终候选，当前不预先认证。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅新增固定v6身份与严格CI日志传输读取；原主实例/网关/控制器/锁和恢复拓扑未变，01部署与12资讯图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"v6复用版本4事务、全账号索引哈希和BirthFence，未新增账号/HTTP/权限/节点；原私网与数据流图保持准确。","diagrams":[]} -->

最终逐job修复后部署/网关三模块1187 PASS、77.13秒；独立backend复跑1047 PASS、54.62秒，reader独立19 PASS。Ruff/Black/isort四文件PASS。未认证的候选CI、合并与部署仍由后续精确回执绑定。
