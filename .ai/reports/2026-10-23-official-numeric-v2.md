# 官方数值合同 v2：离线实现交接

宿主 macOS；任务类型功能开发；范围为现有 DataHub 三个固定公开数值端点的解析、准入和缓存版本。
没有执行网络、SDK、读取凭据、真实数据库、安装依赖或 Git mutation；真实 Host/PG/CI 验收由主任务负责，当前 NOT_RUN。

NYFed rates 保留六种利率、原数值、日期和修订标志；Treasury cash 保留全部原现金列与结构性 null，
仅在官方 meta 同时声明类型和百万美元格式时设置 USD_million。WorldBank 固定 WLD 年度通胀身份、年份与分页。
NYFed 百分数/交易量单位依据官方 CSV；SOFRAI 独立数值单位未确认，保持 provider_defined。
没有补造公布时点、历史版本、完整历史或正式回测资格。

严格 any-null WorldBank value → partial/numeric_values_missing，原 row/raw 保留；Treasury 每行至少一个现金值有效即可，
close_today_bal='null' 不补零。真实初始 Treasury 样本两行但 total-count=4/total-pages=2，只能 partial，不能入原生仓。
未知过滤语法、错误封包/HTML、错身份/日期、重复观测和不一致分页均失败关闭。默认 query 与旧显式会话证据保留。

授权配置摘要不变；v2 仅参与三个固定端点 Host schema/units 身份及新查询 session cache 合同匹配。
旧 DatasetRef/冻结包仍由既有接口读取，旧 call_id 回执原语义保留；新 as_of 不回落旧合同。

离线固定样本来自本任务 logs/first-numeric-probes/{nyfed,treasury,worldbank}.json 的 base64 原公共响应，
复制到 tests/research_web/fixtures/official_numeric/*.json。变异测试另覆盖错误封包、日期/身份、重复、分页、null、空集合和过滤。
tests/research_web/test_datahub_official_numeric.py 还覆盖真实 Broker 的旧缓存跳过/新缓存命中、旧 call_id、
原生准入、freeze/export_restore 原字节及 metadata、backtest 拒绝和版本键隔离。

首轮红灯：logs/official-numeric-red.log（19 failed / 7 passed）。
实际目标回归与静态结果以 logs/official-numeric-test.log、logs/official-numeric-static.log 为准，主任务完成最终候选后须重新绑定源码哈希。
最终目标闭包 188 passed / 12 subtests passed（5.02秒）；包括 DataHub catalog、warehouse management，
不能替代真实厂商/PG/CI验收。ruff 与 black 六文件检查通过；文档治理无违规；Python索引首轮stale，
正式生成 docs/generated/py_file_index.md 后复验通过；Router必需四模块JS测试113项通过。

Router计划 logs/official-numeric-verification-plan.json 为 L4/unknown_impact_boundary，保留必需
Project Constraints CI=NOT_RUN；无桌面/Windows/Linux产品dispatch。没有降级该门或使用旧CI认证。

安装合同：本次无依赖变化；requirements/web.in、web.lock、scripts/setup_web.py、安装文档与bootstrap workflow无需改动，
它们的干净安装兼容性仍由同候选 Mac CI 单独证明，本离线回归不声称已证明。

## 既有 CI 测试登记补充

仅在 `.github/workflows/research-web-checks.yml` 现有 Python contracts 的明确 pytest 模块清单中，
紧邻 `test_datahub_numeric_sources.py` 添加 `test_datahub_official_numeric.py`。没有新增
job、runner、依赖、timeout 或触发条件；仍使用原 `--confcutdir=tests/research_web` 边界。
本新增模块只进行离线 MockTransport／内存仓验证，不访问供应商、真实凭据或 PostgreSQL。
本次补充保持四个宏观源文件与已冻结源码 SHA 不变，不执行 Git mutation 或远端 Actions。
本地登记验证日志为 `logs/official-numeric-ci-registration.json` 与
`logs/official-numeric-ci-registration-tests.log`；实际 CI PASS 仍需 root 绑定最终候选另取证。
