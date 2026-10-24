# 公开 SDK 代理与宏观、财务原件绑定

macOS Web 功能开发；隔离 worktree、临时 owned PG 与有限免费请求。现有服务、正式数据库5432、系统代理、外盘、凭据与模型不操作，无新增依赖。真实取数/入仓/独立进程重启与空库恢复、评审、同候选三CI和Mac安装分别留证，源码检查不替代供应商成功。

三项假设依次验证：requests继承系统代理、SDK端点自身不可用、验证脚本干扰。无网络检查证明空环境仍选择三个本机代理，trust_env=False后为零；不记录代理值。真实子进程与真实requests设置合成回归先失败，再在public_worker的既有有界request包装中关闭继承、清空子进程session/调用代理，保留4秒网络/12秒进程上限。仅匿名AK公开worker有效，宿主及账号SDK不改。新增策略日志曾误入stdout被codec回归拦截，已放进stderr重定向区，JSON协议保持单包。

中国宏观与新浪利润表升级来源合同v2，Provider与仓库复用纯原件投影、全部字段和静态字典声明，逐项绑定来源URL、请求、行、总数、分页、参考时间及first_observed/非PIT声明。旧会话缓存拒绝冒充v2；旧call_id/冻结材料保持原义。GDP累计金额/累计同比不当作BEA单季QoQ SAAR；GDP单位仍未知，不由字段名或数值量级猜亿元/百分数。仅既有M2等已核字段保持原单位。新浪有限8期/总117期的snapshot仍允许，金额尺度、币种/累计与合并口径未知，披露日仅自然日精度，不能提升精确可得时刻。

合成缺陷和修复日志保留：旧入仓守卫可接受被改写的GDP单位/数值及新浪披露元数据，新增反例先6失败；GDP单位不当升级经根代理复核后恢复None，三失败及修正记录保留。真实验收脚本经独评发现宏观缺transport时必败，修为可选值而非伪造生产元数据。当前真实验证待源码冻结后一次性执行；已有成功旧样本不转写为本轮成功。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只收紧既有匿名worker内请求策略及原生研究仓原件绑定；Host、Broker、SDKworker、Provider、可选仓节点与数据边不新增，无HTTP路由、表、依赖、服务或引擎变化。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks同一Python步骤追加一个离线合同模块，保留同候选三CI与MacBootstrap，不新增job、runner或验证节点。","diagrams":[]} -->
