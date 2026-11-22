# 中国宏观四series原生快照

macOS功能开发。实现范围providers_akshare/catalog/broker及原已登记测试、公共响应fixture、模块文档。
未执行真实网络、SDK、凭据、PG、安装或Git mutation。root后续明确扩权允许仅AKfactor_macro
修改__init__/research_warehouse/research_snapshot_store的schema/cache/准入；原official3分支
语义保持，providers_external.py字节不变。此前冻结属于此前候选，当前统一重新冻结完整scope。

root实测macro_china_cpi/gdp/pmi/money_supply分别225/83/225/225行，仅证明该次SDK样本。
实现采用相同固定datacenter-web URL、reportName/columns/pageSize2000直接HTTP，一次请求不翻页，
保留HTTP原字节、success/code/pages/count封包与精确字段，避免SDK丢envelope/数值errors=coerce。
不是新增引擎或独立来源，仍由原owned public_worker执行，容量/12秒子进程/15秒Provider截止不变。

仅cpi/gdp/pmi/m2与真实ISO起止日期；assets/dates/未知参数、回测或供应商历史as_of拒绝。
按月/季度观察期期末裁剪，原REPORT_DATE/TIME不改；GDP严格年内累计，非单季金额。
月末/季末是派生参考期，不是发布时间。缺失不补零、不造历史vintage，不认证formalPIT。
单页完整envelope为snapshot，分页未完、数值null或请求窗无观测partial，不进完整native仓。
CPI指数/累计指数/增长、PMI指数、GDP累计金额/增长逐字段semantic分开；未核单位None，
M2/M1/M0数量按已核亿元标CNY_100million。fields、schema_version=akshare-china-macro-v1
与raw沿原生freeze/export_restore保留，正式backtest拒绝。

不改变其他AK能力v6语义或授权配置摘要；仅AKfactor_macro的Host schema/units身份加入独立版本，
新session查询schema_version不匹配就跳过旧缓存；旧call_id与显式冻结证据按原身份可读。
native额外拒绝非snapshot、旧schema、分页不完整、null、missing或空行；新asof不回落旧键。
Broker正确路由和catalog
明确列出四series；未新增外部可配置入口、依赖、服务或存储schema，原Host/DataHub/worker/
ResearchWarehouse图的节点与边不变。CI复用原已登记测试模块，不新建job/timeout。

离线证据日志china-macro-red.log记录编辑前真实失败；china-macro-test.log及static/black/docs/index
记录最终实跑。新增反例拒绝成功HTTP错误封包、rc/code布尔假零、字段/日期/身份不一致、
坏数值、null、分页自洽失败，覆盖Broker与四series native冻结/独立恢复/raw字节。
另补资金流真实子进程封装及rc100/data=null不入仓/无成功缓存，真实资金流当前FAILED，
详见同日fund-flow报告；中国宏观真实Host/PG与最终CI由root在源码冻结后另取证。

最终离线八模块217 passed / 71 subtests passed（5.26秒）；JS政策/架构四模块113通过。
九文件ruff、black与文档治理/生成索引通过。新反例明确0保留为有效值、null保原值并partial、
缺字段失败；原格式/斜杠/非法日/布尔日期均HTTP前拒绝。新native/schema/cache测试核验
schema/units身份独立、授权scope不变、旧receipt可读、旧session不新命中、null/分页/旧schema
不入完整仓。真实child/codec离线封装通过，但不替代真实供应商或HostPG证据。
