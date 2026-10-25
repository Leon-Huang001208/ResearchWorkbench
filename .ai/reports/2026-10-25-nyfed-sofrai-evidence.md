# NYFed SOFRAI 字段、计算口径与历史可得性

macOS Web 功能开发，独立 worktree、默认 Host 与 owned socket-only 临时 PG 验收。现有服务、正式库5432、外盘、账号与生产模型不操作，无新依赖或付费。真实取数、入仓、三进程重启/恢复、独立评审、原三CI和同候选Mac安装分别取证；未执行不标PASS。

## 官方依据与实现

已保存五份原始HTTP解码正文：NYFed方法页、均值/指数页面、2020发布声明、页面真实链接的API文档及其Swagger YAML。HTTPX直连方法页TLS超时原样保留；系统curl取得完整原文并校验SHA，不把部分下载的Angular脚本或未取得的公式PNG当作依据。字段Schema的sofrai-record将SOFRAI类型、三个average字段和index绑定为number，revisionIndicator为string，search起止日均包含。

三个30/90/180日历日窗口是ACT/360年化复合平均，营业日复利、非营业日按前营业日利率单利，起点跨周末/假日按对应剩余日数处理。发布值为百分率、五位小数。指数是无量纲累计因子，以2018-04-02的1为基准、八位小数；均值不从已舍入指数重建，第五位相等不保证。原始数值不重算或强制转换，其他五类利率原字段保留。

SOFRAI自身value date与其常规发布日在同一营业日；隔夜SOFR的value date则在发布日之前。约08:00ET之后发布、约14:30ET同日修订是规则，不是逐行实际可得时间证明。2018指数基准与2020-03-02首次正式发布分开，revisionIndicator不解释为修订时间或版本链。当前捕获保持first_observed、PIT与正式回测false，未从日期或发布日程制造available_at。

NYFed单独切nyfed-rates-native-v3；Treasury/WorldBank保留official-numeric-v2。新查询跳过NYFed旧v2缓存，旧显式证据不改写。生产和入仓共享严格原件投影、字段与固定metadata；重复JSON键、错误日期/类型/scope、篡改行/字段/元数据/引用/来源、超限及深层递归拒绝，原好快照保留。模型插件不能凭元数据自行提升PIT。

## SDK原端点诊断

当前官方AKShare main源码与已装1.18.94的个股资金流源文件相同。新增三项单变量请求：删缓存时间戳、去固定旧UA、换600000证券，仍均在取得响应头前RemoteProtocolError。因方法页存在Python/native客户端差异，再用原URL/证券/UA/HTTP1.1和同业务参数进行一次系统curl对照，返回空应答(exit52/HTTP000)。四案无重试、未取得业务数据，不支持归因单一Python客户端或账号。SDK原端点仍未恢复，CAUSE_UNDETERMINED；没有修改地址、UT、代理、site-packages或伪造成功。

## 当前阶段

新增合同RED后GREEN，规格评审发现metadata规范化在try外并复现六类异常，再将全部规范化纳入受控异常边界；完整性/非PIT校验未放松。邻近六文件325例通过，ruff/black/isort通过。真实Host/PG及最终候选本机、独评、CI/Mac状态以随后精确SHA回执为准。

官方来源：[方法](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates)、[产品页面](https://www.newyorkfed.org/markets/reference-rates/sofr-averages-and-index)、[发布声明](https://www.newyorkfed.org/markets/opolicy/operating_policy_200212)、[API文档](https://markets.newyorkfed.org/static/docs/markets-api.html)、[API Schema](https://markets.newyorkfed.org/static/docs/markets-api.yml)。固定SHA在providers_nyfed_reference.py及私有原件回执。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"沿原外部Provider/Host/可选研究仓增加NYFed专用语义版本和原件重建，没有新服务、HTTP、表、依赖或执行引擎，原数据流图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks同一步新增一个离线测试模块，无新增job/runner/timeout；原三CI及同候选Mac安装保留。","diagrams":[]} -->

## 第一次真实捕获失败与修复

源58bce994592c384318c2998f81f0ae41f30e1426，单次实际HTTP取得6种记录，任务捕获阶段3.521秒失败于warehouse_persisted=False；未执行后续重启/恢复。默认Host/Broker添加的execution_authorization_digest、quality_accepted、execution_attempts不属于供应商固定字典，旧guard误将其全部拒绝。原失败、raw、HTTP1/SDK0计数和marker保留，owned PG已停并移除；未把该请求提升为入仓PASS。

修复先以默认ResearchService/DataHub/Broker/Warehouse/Series真实链离线复现（只替换HTTP运输与PGbackend，无mock整个send/fetch/ingest），RED后仅将三个精确框架key校验类型并分离；完整meta仍先canonical，剩余来源metadata保持严格等值。未知extra、原件/行/字段/引用/PIT伪造仍拒绝。这些运行态字段不用于授权且不进持久化白名单，首次观察和非PIT标志的既有读取语义保持。332项邻近回归通过；重新真实取数须新源码与独立repair1预算，原marker不重置。
