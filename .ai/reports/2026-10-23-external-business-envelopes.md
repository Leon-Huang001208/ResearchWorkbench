# 外部业务封包误报修复

macOS窄范围功能修复，初始scope仅providers_external+已登记numeric_sources测试/公共fixtures/
vendor-snapshots文档；root后续明确解冻__init__的四pair缓存校验、broker的自动选源错误优先级。
未联网、未取密、未调用SDK/PG、未安装依赖或执行Git mutation；不猜签名、不增加独立数据源。

真实HTTP200反例：Nasdaq rCode400/data=null，CLS errno10012签名错，Dan业务数组空只有参考线；
原件来自logs/remaining-public-probes/ext_{nasdaq,cls,danjuan,kapsarc}.json的base64，精确复制
tests/research_web/fixtures/external_envelopes。错误码与空数组不再发布为snapshot业务行。
Nasdaq/CLS成功码但无已核业务结构、Dan非空历史字段尚未核实均明确schema_unverified失败，
不编造tradesTable/totalRecords或PE/日期字段；真实成功样例NOT_RUN，synthetic反例明确标识。

Dan空数组用partial/no_observation_rows保留原件，避免Reliability对empty的接受语义将它误认成功；
Host两次新call均data_success=False且不成功缓存，旧call_id原回执可读。四pair仅新缓存需
schema_version=external-envelope-v1，旧假snapshot不能供新query复用，配置授权摘要不变。

KAPSARC仅production按专用分号CSV四字段解析，保留原字符串与raw，拒错表头/额外字段/无身份/
无效或未来年份/非有限及负production/重复业务键。0保留为有效量，单位provider_defined；
不推完整历史，也不改全局CSV分隔符。四端点未进入PUBLIC_NUMERIC，不扩native仓/回测/PIT。

Quality发现中国macro新增候选将已配置Tinysoft的factor_series_unsupported覆盖为AK的
generic data_not_equivalent。现在后续generic不覆盖已有具体错误，并保留来源文案；原
test_auto_selects_only_supported_tinysoft_adjustment_series断言未改且通过。新增已支持cpi
auto能跳过Tinysoft选AK，explicit AK不支持仍是自己的data_not_equivalent。

编辑前18 failed/43 passed见logs/external-envelope-red.log。离线已注册测试覆盖真实封包、未知
正码合成反例、边界CSV/零/参数路径/旧cache与receipt、原生仓仍不准入。最终验证日志为
external-envelope-test.log、static/black及相关docgov/policy日志，整批源码最后由root重冻并重跑
8case真实HostPG。既往8case PASS仅属于旧冻结，不冒充本修复后的真实验收。

最终离线九模块288 passed / 71 subtests passed（6.86秒），四组JS政策/架构测试113通过；
五文件ruff/black、文档治理通过。原Broker具体错误回归包括在此次完整闭包内，未排除。
无新增测试模块；所有新增测试仍在Checks已登记清单内，不增加job/依赖/timeout。

没有新增引擎/服务/HTTP入口/依赖/存储schema；现有图节点和边保持。新helper需要root最终
统一更新docs/generated/py_file_index.md，遵守当前本worker不改China SPEC列明docs的边界。
