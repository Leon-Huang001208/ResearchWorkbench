# KAPSARC/BGS 原生宏观实物量与只读Git诊断

macOS功能开发，隔离warehouse/新进程/PG重启/恢复与原三CI及同候选Mac验收；现有服务、生产库、外盘、秘密、模型不操作。真实Host验收已执行见后；最终候选CI/Mac仍待绑定。旧CSV和metadata预检不单独当作入仓证据。

固定CSV原件与官方metadata校验单位kg、来源BGS、Public分类、四列和本次条数，原字符串、元数据时间和原件保留。source metadata stale说明1970-2022与旧CSV实际1971-2023分别记录，不冒充公布时间。矿产年度实物产出不与月度ETF需求/流量或单基金持仓归并。原站BGS同国家/2010单点的单位和数值与旧CSV相符，但同一上游、subcommodity缺省编码及注释/精度字段不等价，不提升到全局或历史PIT认证。

已复现CSV-only旧合成transport不满足新的双响应合同；保留旧解析器兼容断言，新调用必须验证metadata，不能伪造单位或放宽规则。SPEC发现projection_scope没进持久化白名单，root补保留并加仓库/恢复回归，旧快照不补造此键。初轮测试误将旧limit=5当原始完整fixture条数，已修正4128计数，失败日志保留。

Git只读调查报告源在私有证据目录。当前/历史执行器无timeout、maxBuffer64MiB，spawn.error先为COMMAND_FAILED；首次OBJECT_INTEGRITY_FAILED缺退出码/signal/stderr，59927字节1083行归档仅dangling且exit0，官方复查和最后收尾通过。原因仍CAUSE_UNDETERMINED，不执行对象/refs修复、prune/repack或服务操作，日志缺口不在本只读授权中改造。

官方字典：[KAPSARC](https://data.kapsarc.org/explore/assets/production-of-gold-mine/)、[BGS API说明](https://www.bgs.ac.uk/mineralsuk/statistics/world-mineral-statistics/world-mineral-statistics-data-download/)。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"仅在既有KAPSARC来源Provider内部绑定固定元数据与CSV、沿已有原生仓白名单保存，未新增服务、HTTP路由、存储表或拓扑节点，已有03/04/09图保持准确。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks同一步新增两个离线模块且保持原三CI和同候选MacBootstrap，不新增执行拓扑、runner或job，现有验证架构准确。","diagrams":[]} -->


## 真实完整导出验收

源码c1dc9d91c6ac9a57ee20558beba16efeab5fcf6c，6.440秒PASS：一次Provider执行、CSV/metadata两次HTTP200，4128行、124个原country标签、1971-2023参考年。capture/reopen/restore分别PID15598/15636/15640；首进程退出后owned PG真实停止/重启，第二进程重建默认Host读回全部分页，第三进程将冻结包恢复到同一owned集群的第二空库并读回。行/字段/两原件哈希和projection_scope一致，后阶段HTTP0；source/helpers共360份哈希不变。默认仓库工厂和真实psycopg未替换，只允许owned Unix/65473/库白名单/空密码，TCPoff/fsyncon，5432未接触。PG/数据目录/HOME/Host已清理，无凭据或模型操作。

回执SHA256=d55e8315085003b77252a8bf509941623f75317feab74fe5ab8cdc9ed9fa1fbe。本次CSV与旧原件SHA相同，和BGS原站France(French Guiana)/2010单点千克值一致；仅有界同上游校验，不是独立供应商或全量等价，subcommodity缺省编码、注释/精度及历史公布仍未验证。不把metadata日期当行级披露、矿产kg当ETFtonnes流量，正式回测继续拒绝。原始数值只保存在ignored/private证据，Git记录范围与哈希。

本地1165 Python/99子测试、397 JS及五运行源码静态、完整changed-set文档/约束/索引均PASS；原L4/三CI/Mac门保留。最终独评和CI尚待exact候选认证，认证页面/常驻部署NOT_RUN。
