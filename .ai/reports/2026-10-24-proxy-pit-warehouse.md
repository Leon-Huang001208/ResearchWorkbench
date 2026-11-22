# 公开 SDK 代理与宏观、财务原件绑定

macOS Web 功能开发；隔离 worktree、临时 owned PG 与有限免费请求。现有服务、正式数据库5432、系统代理、外盘、凭据与模型不操作，无新增依赖。真实取数/入仓/独立进程重启与空库恢复、评审、同候选三CI和Mac安装分别留证，源码检查不替代供应商成功。

三项假设依次验证：requests继承系统代理、SDK端点自身不可用、验证脚本干扰。无网络检查证明空环境仍选择三个本机代理，trust_env=False后为零；不记录代理值。真实子进程与真实requests设置合成回归先失败，再在public_worker的既有有界request包装中关闭继承、清空子进程session/调用代理，保留4秒网络/12秒进程上限。仅匿名AK公开worker有效，宿主及账号SDK不改。新增策略日志曾误入stdout被codec回归拦截，已放进stderr重定向区，JSON协议保持单包。

中国宏观与新浪利润表升级来源合同v2，Provider与仓库复用纯原件投影、全部字段和静态字典声明，逐项绑定来源URL、请求、行、总数、分页、参考时间及first_observed/非PIT声明。旧会话缓存拒绝冒充v2；旧call_id/冻结材料保持原义。GDP累计金额/累计同比不当作BEA单季QoQ SAAR；GDP单位仍未知，不由字段名或数值量级猜亿元/百分数。仅既有M2等已核字段保持原单位。新浪有限8期/总117期的snapshot仍允许，金额尺度、币种/累计与合并口径未知，披露日仅自然日精度，不能提升精确可得时刻。

合成缺陷和修复日志保留：旧入仓守卫可接受被改写的GDP单位/数值及新浪披露元数据，新增反例先6失败；GDP单位不当升级经根代理复核后恢复None，三失败及修正记录保留。真实验收脚本经独评发现宏观缺transport时必败，修为可选值而非伪造生产元数据。当前真实验证待源码冻结后一次性执行；已有成功旧样本不转写为本轮成功。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只收紧既有匿名worker内请求策略及原生研究仓原件绑定；Host、Broker、SDKworker、Provider、可选仓节点与数据边不新增，无HTTP路由、表、依赖、服务或引擎变化。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks同一Python步骤追加一个离线合同模块，保留同候选三CI与MacBootstrap，不新增job、runner或验证节点。","diagrams":[]} -->


## 实际源码验收

源码22385ece1e23873e9523ed4e3b7a71684cfb2964；attempt2真实5.637秒PASS，3个公开worker、4次HTTP提交。fund_flow的实际Session.send trust_env=False、proxies为空，不再ProxyError；SDK端点ConnectionError仍如实失败，随后访客HTTP200。GDP2026Q3累计、Sina600600.SH/2026-06-30各HTTP200并各选择1行。GDP来源总83条且分页完整，Sina总117期/实际8期的有限snapshot保持分页false；不改成全历史成功。291份源码/helper映射前后相等，SDK/PG二进制另绑定。

真实默认Host/ResearchWarehouse/psycopg、socket-only owned PG18.3/65477，capture/reopen/restore三个独立OS进程；PG实际停启后读回，再向第二空库恢复三份冻结包，行、字段和嵌套原件哈希完全一致，后两阶段HTTP/worker均0。临时PG/HOME/Host已清理，现有5432、系统代理、服务、凭据和外盘无操作。宏观和财务v2首次观测、未知单位和非PIT声明实际保留。回执SHA256=a2ccfd0b01698d6910700a66580771eec91369b9c8847af7bb16d8b0b23359fe。

首次one-shot仅SDK直连1次ConnectionError后，helper的httpx.send lambda命名与Client.stream(request=...)不兼容，未发送guest/GDP/Sina；失败和永久marker保留。修正后的新目录增加真实MockTransport stream/keyword-send纯回归，保存stdout/stderr后才解码，再独评后单次执行。没有重置旧marker、把脚本故障写成供应商故障或隐瞒请求数。

本地完整10组PASS46.116秒（1230 Python/101子测试/399JS）；最终集成候选、评审与三CI/Mac安装另由精确SHA回执认证，当前源码报告不替代这些门。
