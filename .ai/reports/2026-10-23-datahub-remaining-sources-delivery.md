# 能力中心来源验证与宏观研究仓交付

宿主macOS，功能开发；本平台本机及同候选Mac安装CI分别记录。范围为现有DataHub/Broker/公开worker/可选研究仓，不安装依赖、不更新常驻服务、不触碰原5432或外盘。用户确认无Tushare账号，继续免费来源；没有采购、账号注册、真实模型调用或新增账号探测。

## 变更与结构复核

官方NYFed/Treasury/WorldBank封包采用明确身份、日期、数值和分页校验。中国宏观在AK现有factor_macro链路只开放cpi/gdp/pmi/m2，保存原始HTTP响应并区分月度参考期、累计GDP与来源单位。新会话缓存、仓库逻辑身份和原生准入分别核对合同版本；历史call_id和冻结包保持原含义。单股资金流保留原SDK并增加同上游guest后备，但当前真实响应失败，不认证其可用或入仓。

核对02模块图与04数据流图：04的normalize节点已包含可选研究仓、修订和冻结，Provider到既有worker/上游、原生捕获到冻结的边仍覆盖本轮行为。没有新服务、HTTP路由、数据库表、持久化根或执行引擎；因此无需改画拓扑。ARCHITECTURE、DEVELOPMENT_MAP及DataHub组各模块文档补充具体合同及限制。公开封包修复仍在原Provider与缓存边界，不新增数值仓准入。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复核既有02模块及04数据流图：Provider仍经原公开worker读取上游，04 normalize节点已覆盖可选PG原生捕获与冻结；本轮只增加封闭序列、封包校验和逻辑合同版本，无新服务、路由、表或持久化根。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅在既有Research Web Checks同一Python步骤加入官方封包测试，其余测试扩展已登记模块；未改变job、runner、超时、门、依赖或平台归属，08迭代验证图仍覆盖相同本机评审与CI交付流程。","diagrams":[]} -->

## 实际验证与边界

逐项台账见`2026-10-23-datahub-source-verification.json`及`2026-10-23-remaining57-actual-validation.md`。57项全部核对状态，不等于57项可用；运输失败、错误业务封包、HTML、空参考线、缺实现、账号及设备分别记录。原始失败证据不覆盖。

首次四case Host proof因验证脚本使用超过500的分页limit失败，已发生的一次WorldBank HTTP请求保留；修正脚本后四case成功，仅验证数据库重启。后续冻结源码470ba717f3f663a7348f05c48ca8bb3cb02ff8774e47b5fee449a116090acf8e的八case实际通过：WB2、NYFed6、Treasury4、AK财务1、CPI3、GDP1、PMI3、M2三行；均写入独立临时PG并跨会话读回相同行/字段。

八case还实际重启数据库、关闭并新建ResearchService，验证新Host八次库命中且无新增供应商执行，再恢复到另一空库比对冻结摘要。直接HTTP3次，owned worker提交5次；子进程SDK底层HTTP次数没有逐个测量，不能把这些计数相加称全部HTTP总数。零模型调用，socket-only临时PG停止并删除，临时HOME清理。原件位于`logs/final-numeric-host-real/`，绑定当时源码哈希；后续Broker错误码及公开封包修补须对最终候选重新绑定，不能借用此检查点冒充最终CI。

资金流真实Host失败；直接guest诊断曾收到HTTP200但rc100/data=null，保持FAILED，不执行空集合冻结来认证成功。先前成功259字节只作为历史公开样本，不能证明当前接口恢复。BLS POST403及官方GET一次ConnectTimeout均保留。国内四SDK原始样例证明接口可返回，不单独替代Host入仓证据。

## 验收进度

官方合同及中国宏观定点、子进程封装、字段保真、分页/null/版本/撤权反例已执行，详细数量以各冻结SPEC和独立日志为准。独立扩大Broker回归发现旧auto错误码被新增AK候选的通用错误覆盖；原失败日志保留，按兼容旧错误合同修复，不删除旧测试或改弱断言。最终完整changed-set Router、最终源码评审、同候选通用CI与Mac安装CI尚待执行并绑定。

这些数据是provider-native first-observed捕获；没有历史披露链、供应商过去修订vintage或跨源规范投影，就不获得正式回测资格。AK宏观Broker当前连storage_read的as_of也拒绝，Host历史时点查询未认证；显式冻结导出恢复可用。Windows/Linux原生和真实设备保持NOT_RUN；不部署，不移动现有服务或外盘数据。

## 最终源码与本机结果

最终七个改动源码逐项冻结聚合为`f6ba79c554d11b5bd4a3ebcae30d67a44badadbdb50cff7adf7ab9f9bcd4793c`。SPEC复审182 passed/59 subtests；质量独评315 passed/59 subtests，均无P1/P2，原Broker回归已过。详细冻结与日志为`logs/external-envelope-source-spec.json`、`logs/spec-final-envelope-independent.log`、`logs/final-envelope-quality-independent.log`。

最终源码又实际执行八case，原件`logs/final-candidate-numeric-host-real/receipt.json` SHA256=`d6c2726c8e5ec5316d2899c4f28fa6e9182251dcf1ef1d5fc0d9682847501117`。该回执的十源码JSON-map聚合为`031489d891c3c83669e4389171e73a198638c2ed32eaa8a482c5737ea14e6465`，与七源码SPEC清单范围不同；七个交集文件逐项完全相等。八case、字段/行缓存、PG与新Host重启、独立空库恢复全部PASS，source_unchanged=true，原临时库与HOME均清理。先前检查点保留，不覆盖或转写。

KAPSARC最终代码又执行一次实际公开请求，五行已正确拆为四列，状态partial/row_limit；原值、未知单位与非完整历史限制保留，未入仓。Nasdaq、CLS热榜与Danjuan非空业务正例仍未通过，已知错误/空响应不再冒充成功。

Root本机最终闭包433 passed/71 subtests；Router九模块JavaScript共230 passed。七源码及改动测试Ruff、Black、isort均PASS；项目正常silent配置Mypy七源码PASS，但不检查所有未注解函数体，不代表完整类型证明。完整changed-set约束首轮缺少README复核及workflow模块说明，原失败日志保留；补实际说明与两组结构复核后47文件约束PASS，文档治理与Python索引PASS。源码没有为这些文档门改变。最终候选CI及安装仍须单独绑定，当前不写为PASS。
