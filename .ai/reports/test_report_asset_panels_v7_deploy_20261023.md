# 资产副图v7固定部署

任务asset-panels-v7-deploy-20261023；宿主macOS Mac mini，Web部署功能扩展。用户已明确授权验收后更新常驻。

2026-10-23资产副图固定v7部署：封闭apply-assets-v7 / reviewed-asset-observation-v7，PREVIOUS=c4e953c4386c615cde89ad2d014d60c6e2959303，PAYLOAD=3a62ca1a3bff0927db681322a1ff028f08cf03cd（含PR204资产及PR203财务补齐的组合产品）。沿原version4事务、维护锁、BirthFence、64MiB严格业务索引/全账号保全及恢复；额外复用现有市场inflight空闲检查。旧v1–v6、market、模型身份和controller/evidence字节保持。锁文件7c631d4f、严格reader5c3077固定，无新依赖、HTTP、schema或权限；仍须新操作员同候选独评/完整Router/三CI/Mac安装及实际部署证明。

本轮仅增加封闭固定profile及原参数化回归，产品已合并PR204。业务数据、会话、报告、账号、凭据、外盘及数据库保持；不调用模型或供应商。实际新操作员本地/独评/同候选三CI、持锁部署与认证页面证据分别取得，不预先标记已部署。Windows/Linux原生由对应真机交接。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅为原Native联合升级器新增固定v7身份，原主实例/网关/控制器/锁和version4恢复拓扑保持；没有新节点、HTTP或数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"v7复用全账号索引冻结/保全与BirthFence，只增加现有市场inflight检查的模式绑定；不改变账号、权限、私有池或数据归属。","diagrams":[]} -->

本机升级器+网关1301项通过（88.64秒）；独评指出v7市场inflight覆盖未进入持久参数表，已补入正式用例，临时独验15项通过。修改文件Ruff/Black/isort及operator Mypy follow-imports=skip通过；未把此有限静态范围称为全项目Mypy通过。

主线在初次v7候选三CI通过后合入PR203财务能力，原候选保留历史但不用于最终部署。尚未合并的v7 PAYLOAD修订为3a62组合检查点；其PR203已有两项通用CI，不能称Mac安装通过，最终组合仍重新执行原三CI/同候选Mac安装。PREVIOUS继续实际c4e，旧profiles/reader/controller/依赖锁不变；新字段需独评与组合回归。
