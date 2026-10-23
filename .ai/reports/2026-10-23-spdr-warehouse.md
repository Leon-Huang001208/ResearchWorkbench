# SPDR GLD 原生研究仓接入

宿主macOS，功能开发；任务datahub-spdr-warehouse-20261023，基线PR203 merge3a62ca1。
现有服务、正式5432库、外盘、账号和模型不操作，无新依赖安装。原三CI和同候选Mac安装门保持。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"SPDR沿既有external_data/gld和ResearchWarehouse/SnapshotSeries路径增加四项原生投影、原件绑定与版本身份，无新HTTP路由、数据库表、服务、存储根或引擎；原Host/Provider/可选仓节点与边准确。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只向原Checks同一Python步骤加入两模块，原job、runner、时限和原三CI保持；真实公开HTTP及临时PG独立验收，08流程图准确。","diagrams":[]} -->

## 合同与阶段证据

- ext_spdr/gld只投影total_nav_usd、total_tonnes、total_ounces、shares_outstanding，专用spdr-gld-trust-snapshot-v1。
- 参考日期独立保存；USD/tonnes/ounces/shares为原标签，精确小数字符串和原始格式均保留，不转换重量标准、币种或份额。
- 只接受空arguments；非空query/params/body容器也拒绝。as_of/backtest/required_semantics在网络前拒绝。
- 原件重解析后逐项核对行、字段、单位及版本；新查询跳过旧缓存，旧显式回执可读。
- 真实直接公开预检HTTP200/2362字节，sha256=3791bbf7f86aac01255eed454d7bc2739e3ee130b86a3fdd370ebd7f757ef01b；只证明当前响应四项有值有日期，未由此认证Host或研究仓。
- Provider先RED，最终定点212通过；仓库接入先3 failed/15 passed，原件测试误读双层封包失败另保留，修正为按冻结批次解析后18通过；增加四项总数拒绝后联合118通过。

正式历史PIT、跨源等价、全历史、认证页面、CI和部署均未由以上合成检查认证。真实Host入仓、重启及独立恢复待执行。
SPDR网站的交易日持仓与金条清单的结算日口径分别保留；四项持仓快照不当作资金流指标。

参考：[GLD官方页面](https://www.spdrgoldshares.com/usa/gld/)、[官方FAQ](https://files.spdrgoldshares.com/spdr-cms/2026-03/GLD-FAQs-January-2026.pdf)。
