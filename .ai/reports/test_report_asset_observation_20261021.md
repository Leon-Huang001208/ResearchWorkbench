# A 股资产观察：行情主屏与研究专题

任务：`asset-observation-20261021`。宿主：Mac mini / macOS；类型：Web 功能开发。当前状态：IMPLEMENTED_PENDING_ACCEPTANCE。基线：`8d2f5bb40c69a463ba8a24c045926b056e41b3c2`；最终候选、CI、评审与收尾在完成后补记，不复用基线证据认证新代码。

## 结果与边界

实现独立资产列表、资产身份与来源时间、SVG 行情主屏、报价指标及七个研究专题。新闻和公告由研究情报迁入资产页，旧地址继续重定向，沿原只读 GET 查询；其他资产类型保留既有能力边界。财务参数按实际来源等价转换，保留 Wind 60 日硬限制；新增两融、股东汇总与显式单区块刷新。

不新增数据供应商、依赖、数据库、执行引擎、自动模型调用或实时行情承诺。AlphaFoundry 只用于理解既有交互与数据转换；未复制其协调器、规则委员会、合成主题或共享 Excel 工作簿行为。常驻服务未部署。

## 实际验证

- `node --test tests/javascript/research_web_asset_workspace.test.mjs tests/javascript/research_web_asset_chart.test.mjs tests/javascript/research_web_workbench.test.mjs tests/javascript/research_web_intel.test.mjs`：48 项定点回归通过；Node 24.19.0 的 CI 同命令总计 763 项、761 PASS / 2 SKIP / 0 FAIL，日志 `logs/asset-js-ci-parity-final.log`；缺口先红后绿，评审负例日志 `/tmp/rwb-asset-review-red.log`。
- 已有 Python 测试解释器运行 `python -m pytest tests/research_web/test_asset_workspace.py tests/research_web/test_datahub_wind.py --confcutdir=tests/research_web -q`：100 PASS，14.88 秒；日志 `logs/asset-python-final.log`。取消、保存失败、恢复及活动 owner 均有离线真实控制路径回归；不连接供应商或 Excel。
- `node tests/e2e/research_web_asset_workspace.mjs`：6 个隔离浏览器场景 PASS，覆盖 1920/1200/390 宽度和明暗主题；包括图表键盘/叠加、专题、分页读取、资讯转义、新闻焦点及笔记草稿、资产切换身份。截图与摘要位于 `logs/asset-observation-20261021/`，日志 `logs/asset-browser.jsonl`。全部是显式 fixture，不是行情或模型质量验收。
- 原系统 Python 与主 checkout `.venv` 缺 pytest；复用既有已安装测试环境，无安装或修改依赖。后台 Python 评审的全依赖 mypy 存在未改动模块错误，不能标记整仓 mypy 通过。

## 评审问题与修复

- 顺序查询取消及启动前取消后结算全部 loading，防止刷新永久 409。
- 刷新受理保存失败精确回滚内存及幂等键，不启动未知供应商请求。
- 同进程重复构造不恢复仍由实际活动 Task 持有的观察；原产品单 Web worker、单数据根所有者边界继续适用。
- 渲染器校验完整资产身份，资讯独立局部重绘，保留当前资产的表单草稿和键盘焦点。
- 恢复标准 DataHub `turnover` 成交额别名，换手率仍只用独立字段；无完整周期不输出指标。

## 待完成

本地完整 Router、项目完整性和文档同步检查已执行；完整结果保存在 logs/asset-local-gates.json，首次 UI 集成失败与修复证据同时保留。最终候选独立评审、GitHub 通用门、同候选 macOS Bootstrap、PR 合并与资源收尾由后续绑定最终 SHA 的交付回执认证。真实 Wind 调用、Windows/Linux 原生及跨平台发布保持 NOT_RUN；不阻断独立完成的本平台任务，但不得改判为支持。

## 架构决定

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"资产页在既有原生 Web UI 内拆分控制器和 SVG 图表，复用主导航、账户作用域与同源 API；没有新增进程、服务或权限边界，原系统级 UI 依赖图仍适用。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只修复既有 Broker 到 Wind Provider 的等价参数并公开实际快照元数据，未注册新供应商或能力，也未改变 Host 到 Provider 到会话快照的边界。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"资产观察在现有 Store 和 AssetWorkspace 内增加可选区块及幂等刷新，旧快照不重写；研究交接仍使用原 DataHub 快照和唯一 DSH，不增加执行或数据存储服务。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"沿用原检查、runner与macOS Bootstrap；资产回归和受管Git恢复状态处理保持原强校验与修补计数，无新增作业、执行器、调度或权限边界。","diagrams":[]} -->

## 用户追加授权：天软 CJPY 实际数据

用户授权使用 CJPY 真实数据，并允许检查 AlphaFoundry 既有配置。确认其 SDK 本机凭据可用；不输出凭据，不修改或迁移到 RWB 常驻/账号配置。以临时连接回调运行真实 AssetWorkspace → DataHub → Broker → CJPY → 会话快照，仅查询 603986.SH 的概览和历史两区块，固定 tinysoft、无自动换源或模型调用。

真实结果：概览 1 行，历史 9 行，历史数据日 2026-10-08 至 2026-10-20，概览数据日 2026-10-21；两个区块 complete。保留供应商原字段与未知单位，结果文件 logs/asset-cjpy-live.json 的 SHA-256 为 543d54a61306039b5fddb01a45d0410769c49a398ce9903d591314c7abb05d58。验收 Store 与私有控制文件使用独立临时目录，在公开数据证据保存后回收；现有业务数据、全局 SDK 配置与模型均未改动。

实际数据发现并修复两个原有边界：业务周期/复权需要等价映射到 CJPY SDK 值；CJPY 的日期/名称/成交量原字段需要 UI 识别。新增离线负例先红后绿。真实取数不等于产品已保存天软连接，也不证明 Wind、财务、盘口或模型质量。

真实 CJPY 保存快照的桌面明亮/窄屏深色浏览器回读 2/2 PASS，9 根真实 K 线、证券名称和实际数据日均已核对；回读过程没有再次调用供应商。证据 logs/asset-cjpy-browser.log 与 logs/asset-observation-20261021/cjpy-real-summary.json。当前涨幅可由同一快照的 close/yclose 明确计算并标注，交易指标不跨日期补值。

## 最新主线集成

第三轮候选 ef939774 的全部CI已通过（Python1291 PASS/11 SKIP、JS770 PASS/2 SKIP、macOS干净安装），但期间PR169合入master至5ab7bd5，旧候选不能直接合并。原集成工作树合入该基线，保留独立发布仓库身份及主线已审的30分钟CI上限；旧证据保留但不能认证新候选。

受管入口对已发布awaiting_ci/ci_failed的基线刷新曾依赖先做一次publish repair来设置remote_moved，在计数耗尽时无法恢复真实主线前进。补齐为这些状态可直接调用原有强校验prepare，仍要求真实基线前进及原PR/祖先/工作树/锁全部一致，保留旧回执和修补计数；不修改全局工具、不手改回执/计数、不允许同基线刷新。五个回归先红后绿由既有Git安全测试和Project Constraints执行。

保留 `4e8be6ac7405733755e4a00be10898504e71710a` 已合并的业务导航，资产规范地址使用 #/assets；旧 workbench 和个股资讯地址兼容。合并保留主题检索、基金数据、策略模拟及其页面归属/草稿/异步所有者保护，没有回退其他任务行为。复审新增 Wind 快照时点负例：价格存在时只读取该快照 date/时间/as_of，缺失保持未知，不从历史K线借日期；图表局部重绘再核对当前资产身份。

集成检查：Node 24.19.0 的全部 Research Web JS 共 772 项，770 PASS / 2 SKIP / 0 FAIL；原业务导航浏览器验收 10 项通过，本任务 fixture 6 场景与保存真实 CJPY 数据回读 2 场景通过。原 Mac Bootstrap 同一启动步骤增加七个资产静态资源的已安装字节与 checkout 字节一致核验，摘要进入现有最小 artifact；远端运行尚待执行，不以本地检查代替。

## 综合 CI 的元数据扫描修复

修复后的综合 CI 39580017091 在 309.41 秒完成 Python：1274 PASS、11 SKIP、17 FAIL；超时问题已消除。失败集中于两处合同夹具仍替换旧的 _dependency_ready，而真实目录已读取 _dependency_status；Mac 已安装依赖掩盖了该缺口。以 find_spec 全部返回 None 的本机负例复现后，只将这两处夹具改为替换实际依赖边界，仍经过原 AssetWorkspace/Broker/Provider；不安装 Wind SDK、不修改生产目录/Provider 的平台与准入规则。

首次综合 CI 39575611151 达到原 20 分钟上限后取消，未认证为通过；同候选 macOS Bootstrap 39575611311 和 Project Constraints 39575611345 已通过。只读分析发现 5%→11% 段的 1408 次能力 draft→check 累计约 765 秒，其中 576 次超过一秒；该段无凭据失败，不能解释为凭据重试或死循环。本机 cProfile 独立确认一次目录初始化重复调用 packages_distributions 18 次，占约 4.97 秒。

修复只在同一次 CapabilityCatalog 初始化事务懒加载一次模块清单，finally 清除；显式 validate/check、依赖版本、来源和凭据仍保持新鲜检查。新增先红后绿回归覆盖扫描次数、新实例、初始化后依赖消失和异常清除，原禁止导入检查保持；资产 API 测试改用内存钥匙串。原 CI 增加该单项回归，保留全部既有测试、runner 和 20 分钟上限，不重跑旧候选。新候选仍需独立评审和同候选全部 CI。

追加用户授权后，已用原连接保存机制将天软凭据复制到 RWB 主实例系统钥匙串，回读一致，configured/secret_configured 为真、restart_required 为假；不输出秘密，不重启常驻服务。操作回执 logs/asset-credential-transfer.json 保存在主 checkout 私有日志；这一后续配置操作不改变先前临时 Store 的真实取数证据。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"仅在既有目录构造事务内部共享静态安装元数据，事务结束及异常清除；初始化外的准入、来源、版本和脚本检查仍实时执行，没有改变Host/DSH、存储或权限边界。","diagrams":[]} -->

复审修复：新闻/公告内通过更新数据表单改变证券身份时，replaceState 后立即激活该资产资讯，保持行情与资讯并行。浏览器回归先红后绿，六种宽度/主题均通过，日志 logs/asset-news-form-red.log、logs/asset-news-form-green.log。最新主线 c68814db 的部署资格变更已保留；不包含本任务的常驻部署授权。

元数据修复本机验证：完整能力目录、资产和Wind合计121 PASS，46.24秒；仅更新原工具清单的陈旧断言以反映已存在且不可选择的research_check_quality/research_read_source，没有新增工具权限。完整CI Python同清单仍在运行。

额外本机CI同清单探针并未全通过：1275 PASS、27 FAIL，120.24秒。失败集中于未改动的macOS文档沙箱与冻结恢复：借用另一worktree的已安装测试解释器导致site-packages读权限拒绝，以及已安装旧包runtime_contract_unsafe_path；不能据此声称全套本机通过。资产/能力/Wind的121回归已通过，正式必需Router门与干净安装仍分别记录；不放宽沙箱/冻结恢复或修改其他任务解释器，不安装依赖来掩盖这些环境限制。日志logs/asset-ci-python-parity.log。

无厂商SDK负例两项先红后绿（2 PASS/0.43秒），资产/Wind完整100 PASS/6.46秒，Ruff/Black/isort/diff检查通过；日志logs/asset-wind-sdk-absence-{red,green}.log及logs/asset-wind-fixture-final.log。

受管基线刷新完整Git安全回归83 PASS/79.31秒；独立评审额外13个相关守卫通过。新状态仅允许真实前进的基线，旧PR、全部计数、旧回执及所有Git引用保留；日志logs/asset-base-refresh-{red,green}.log。
