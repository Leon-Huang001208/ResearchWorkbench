# 单股资金流同源 guest 后备

宿主macOS，功能修复；只修改AKShare Provider及其已登记测试、模块文档和本报告。
四个宏观源文件冻结不变。未执行真实网络/SDK/凭据/PG/Git mutation/安装操作。

真实Host验收状态由root回填为 **FAILED**：`logs/fundflow-host-real/receipt.json` 与
`direct-guest*` 显示默认、header与omit-ut请求均HTTP200但rc=100/data=null。
原因未知，不追加真实请求或猜测网络/账号根因；早先一条rc0响应不代表当前可用。
本次补齐离线真实public_worker子进程/序列化封装（只替换SDK和HTTP为fixture），以及
rc100/data=null两次Host调用均failed、无成功缓存且native拒入仓的反例。

已知真实现象由root提供：原market_activity/fund_flow SDK在2026-10-19至20请求失败，
logs/first-numeric-probes/fund_flow.json为failed/vendor_unreachable；这是已观察到的错误分类，
该回执没有保留原异常文本，不能据此认证具体网络根因或推断AKShare所有接口失效。
root另实测同Eastmoney guest固定单证券接口
HTTP200仅返回2026-10-22一条，原件/tmp/rwb-fundflow-guest/response.bin，259bytes。
该样本精确复制到tests/research_web/fixtures/fund_flow_guest.json（不补末尾换行）。

最小修复只在原SDK调用实际抛异常后进入guest；成功/空/畸形DataFrame不重试。
guest仍在原owned worker容量与12秒子进程/15秒Provider截止内，4秒HTTP等待，
trust_env=False、禁止redirect及字节上限；不触及市场整体流向或大盘secid2。
请求使用已实测公开ut及原fields1/fields2；code/market和15列合法性、有限数值、
日期顺序/重复/未来日期校验失败关闭。保留HTTP原字节和原净额，不猜金额单位。

有日期请求一律partial，匹配单日也不声明完整历史；无匹配日期partial零rows，
provider_total保实际上游1行，raw保原件。无日期仅snapshot，pagination_complete=False，
声明first_observed、single_response_not_complete_history、same_eastmoney_upstream_not_independent_source，
正式backtest和as_of拒绝。SEMANTICS_REVISION v6复用既有AKShare缓存授权版本机制，
不改宏观源缓存/schema合同，不把同源后备计作独立源。

编辑前离线红灯logs/fund-flow-guest-red.log：1 failed/11 passed/16 subtests，
新增回放因SDK OSError直接上抛而失败。修复后覆盖原成功SDK不访问guest、日期命中及不命中、
identity/envelope/rc/非有限数值/重复或未来日期、HTTP失败/重定向/超时/字节上限、backtest/as_of。
相邻catalog现有共享容量超时/busy/恢复与public_worker进程截止测试仍保留。
实际验证汇总见logs/fund-flow-guest-test.log、fund-flow-guest-static.log，root最终真实Provider
取数当前已由root记录真实FAILED；Host/native仓成功与CI没有被本报告认证。

最终相邻五模块116 passed / 33 subtests passed（4.60秒）；既有四组JS政策/架构测试113项通过，
ruff、black、文档治理和Python索引检查通过。Python索引首轮stale，经正式生成入口更新后复验通过。
本子任务Router计划logs/fund-flow-guest-verification-plan.json保留实际选门；整批最终changed set、
exact候选CI与真实Host/PG重绑由root执行。四宏观source哈希逐项与原SPEC核对保持一致。

无新依赖、服务、HTTP入口或节点，原Host→DataHub→owned public worker→Eastmoney拓扑不变；
原图仍适用，不重画。CI复用原已登记test_datahub_akshare_semantics.py，不新增job/timeout。
