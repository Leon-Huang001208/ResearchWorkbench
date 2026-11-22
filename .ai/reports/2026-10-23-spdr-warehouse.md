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

## 真实Host与独立研究仓

干净源码0b58b545844707aceed8f053bf3679763efd87e6实际执行一次供应商调用、一次已计数HTTP GET，4项投影通过完整ResearchService及内部business-query API进入独立PostgreSQL。使用生产默认仓库工厂；连接guard仅放行已验证的Unix socket/65473/数据库白名单/空密码并原样调用真实psycopg，exercise guard实际计数19次owned连接（不含外围夹具连接）。不是替换仓储backend；临时数据库账号取自该自有实例，不读现有账号。

跨会话display缓存、同进程关闭并重建Host对象、owned PG进程停止/重启后零额外供应商调用读回、冻结导出及同一owned PG实例的第二空库独立恢复并再次读取均PASS，行、字段、日期、单位及原件绑定一致。合法历史与正式backtest请求被拒，未制造历史版本。20.794秒完成；临时PG停止/目录移除、临时HOME回收，模型/RPC0、供应商凭据0，现有5432/服务/外盘无操作。回执SHA256=409982d8d1a43b367753f9dbac0f11f64f8765aa01fef8b5eec1e06b825ec073，全部258个app执行源码/PG隔离夹具哈希前后一致。

原始公开响应和真实数值仅在ignored私有证据保存，Git报告只记哈希、范围和结果；交付时归档并恢复核验。直接预检与本轮Host各1次公开HTTP，不能把预检当Host成功。原四项数据是当前来源快照，金融流量、全历史、跨源等价及正式PIT均未由此认证。认证私网页面/部署仍NOT_RUN。

## 验证过程与剩余门

完整本地Python954/99子测试、JS397通过。初轮校验helper误用base..HEAD，暂存改动下文件清单为空，Ruff意外全仓8137项失败保留；不把未分类结果算作本任务新增回归或通过。修正为完整工作区/暂存changed set后按六Python文件/四运行源码执行静态检查，保留已通过且字节未变的Python/JS证据。完整Router仍L4/原三CI，补齐5份必须模块文档后10项本地检查PASS，未削弱门。

安装合同raw字节对比首次因setup-web.cmd的CRLF与Git blob LF不同失败；改用Git attributes规范化哈希核验6份安装文件未改。纯预检回放首次误用系统Python缺pydantic，未安装依赖，使用已批准环境后成功；这些都不作为供应商失败。真实helper已由独立Python质量审查允许一次执行，最终候选评审/CI/Mac仍待精确绑定，旧候选结果不转写。
