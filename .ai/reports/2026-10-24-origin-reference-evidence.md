# 原端点诊断与单位、累计、历史可得性证据

macOS Web 功能开发，独立 worktree／临时 owned PG。现有服务、正式数据库5432、系统代理、外盘、账号和模型不操作，无新增依赖或付费。源码检查、真实取数／入仓／重启／空库恢复、独评、三CI、同候选Mac安装分别取证；本报告阶段记录由最终精确SHA回执闭环。

## SDK 原端点

唯一一次四案诊断固定同一公开股票及SDK原URL／UA／字段，requests/httpx分别lmt0和lmt30。4 reservation、4 terminal、无重试，未收到HTTP头／正文。httpx两案均完成TCP、TLS、请求头与正文发送，再在接收响应头阶段失败；requests链为ConnectionError/ProtocolError/RemoteDisconnected。不能仅据此认定账号、远端或中间网络责任，也不支持通过缩小lmt或换客户端宣称修复。原端点仍未恢复；访客是同上游后备，不计独立来源。代码为自然SDK失败增加有限安全error_code，并要求资金流v2尝试链存在且满足精确白名单。

## 参考证据

GDP页面观察到的官方JS明确把RPT_ECONOMY_GDP八个字段映射到亿元和百分号；国家统计局核算方法说明金额现价、增长可比价。新宏观v3保存固定URL／SHA／字段映射，金额为CNY_100million、增长为percent，均为年内累计语义，不能当作单季或BEA QoQ SAAR。静态定义证据不证明API历史值在过去时点可得。

发行人2025年中期印刷版PDF第5页（印刷页4）明确600600合并报表1月1日至6月30日、人民币元，集团营业收入和净利润与新浪同证券／期间两格精确相同。PDFKit离屏渲染已人工核对表头、第一列、净利润与归母两行不同；Poppler缺字体映射、pypdf文字乱码不作为视觉证据，失败记录保留，未安装依赖。参考只绑定两格原始十进制哈希和明确scope；原data不改、全局及其他item单位未知。float可能丢失原JSON词法精度，因此不允许获得精确匹配认证；只接受精确字符串／整数，bool拒绝。值或scope不符时单位、比例、合并及累计认证均为空。

新浪本次2025H1记录日期字段为2026-08-27，发行人新闻页声称2025-08-26发布半年报，两者独立保留并标冲突。印刷版PDF的原始发布字节与当时可得时间未证明，不能按URL目录日期回填。所有当前原生捕获仍first_observed、非PIT／正式回测不可用。

参考原件／数值只保存在本机私有证据；仓库冻结恢复验证原始供应商响应和参考元数据，外部PDF／HTML／JS随独立证据归档迁移，不声称其二进制已嵌入每份数值冻结包。

主要原始来源：[东财GDP页面](https://data.eastmoney.com/cjsj/gdp.html)、[页面引用脚本](https://data.eastmoney.com/newstatic/js/cjsj/cn/gdp.js)、[统计局核算方法](https://www.stats.gov.cn/sj/zxfb/202507/t20250716_1960426.html)、[发行人发布声明](https://www.tsingtao.com.cn/MT/news/7cc9514e-bbb1-44dd-b3d7-c57ac18085be.html)。原件哈希和PDF地址在新版本引用ledger及私有记录内。

红绿记录保留：新增参考模块初轮失败、缺失整段attempts未被拒绝、未匹配项仍带basis、JSON浮点折叠错误认证均先复现再修复。真实新版仓库验收计划在源码冻结后执行；当前结果见后节，旧源成功不冒充本轮PASS。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只增加既有AK原生投影中的固定参考ledger、逐格注释和SDK失败码，沿现有Provider/仓库节点，无新HTTP路由、表、依赖、服务或执行引擎；参考原件由已有证据归档保存。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks同一pytest步骤增加一个离线参考合同模块，原三CI和同候选Mac安装均保留，无新job/runner/验证节点。","diagrams":[]} -->


## 实际新版默认Host／仓库验收

源码72167e0d6e794c8dafc4c0df323224df9d13e28b，6.074秒PASS，3个公开worker、4次HTTP。资金流1行（SDK自然连接失败码保留、guest真实后备）、GDP2025Q2至2026Q3六行、Sina600600.SH/2025H1一行。默认ResearchService/ResearchWarehouse/真实psycopg，owned PG18.3 Unix65478/TCP关闭/fsync开启；三独立OS进程、真实postmasterPID改变后的读回、默认Host及相同actor/scope/dataset向第二空库export_restore与新session业务读取。后两阶段SDK/HTTP均0，行/字段/原始字节/参考哈希和冻结包一致，288份源码/helper映射前后一致，依赖包/PG另绑定。PG/数据目录/HOME已回收，5432/现有服务/外盘/账号不操作。回执SHA256=c61610486649603db7de643655b0dc61d3c2ba528adb908abb778f1d51eac9a2。

恢复后六季度GDP单位和价格基础、两格财务参考匹配及2026供应商日期/2025发行人日期冲突均保留；全局未知项和PIT=false不提升。额外只读对照显示当前供应商2025H1 GDP值不同于NBS当年初步发布页，差异可能是修订或供应商映射，原因未证实；不能使用当前值伪装历史可得数据，当前抓取也不证明发布时完全相同字节。参考HTML/PDF/JS和图像另随私有归档迁移。

本机源码阶段完整10组检查67.503秒PASS；最终集成候选的独评、CI/Mac安装与安全收尾以精确SHA外部回执闭环，不把本段源码阶段状态冒充最终候选资格。
