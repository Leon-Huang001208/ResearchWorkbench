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
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅将两个资产数据回归模块加入既有 Research Web Checks 的 Python 步骤，沿用既有 runner、超时、macOS Bootstrap 和平台归属，无新增作业、产品平台派发或依赖。","diagrams":[]} -->

## 用户追加授权：天软 CJPY 实际数据

用户授权使用 CJPY 真实数据，并允许检查 AlphaFoundry 既有配置。确认其 SDK 本机凭据可用；不输出凭据，不修改或迁移到 RWB 常驻/账号配置。以临时连接回调运行真实 AssetWorkspace → DataHub → Broker → CJPY → 会话快照，仅查询 603986.SH 的概览和历史两区块，固定 tinysoft、无自动换源或模型调用。

真实结果：概览 1 行，历史 9 行，历史数据日 2026-10-08 至 2026-10-20，概览数据日 2026-10-21；两个区块 complete。保留供应商原字段与未知单位，结果文件 logs/asset-cjpy-live.json 的 SHA-256 为 543d54a61306039b5fddb01a45d0410769c49a398ce9903d591314c7abb05d58。验收 Store 与私有控制文件使用独立临时目录，在公开数据证据保存后回收；现有业务数据、全局 SDK 配置与模型均未改动。

实际数据发现并修复两个原有边界：业务周期/复权需要等价映射到 CJPY SDK 值；CJPY 的日期/名称/成交量原字段需要 UI 识别。新增离线负例先红后绿。真实取数不等于产品已保存天软连接，也不证明 Wind、财务、盘口或模型质量。

真实 CJPY 保存快照的桌面明亮/窄屏深色浏览器回读 2/2 PASS，9 根真实 K 线、证券名称和实际数据日均已核对；回读过程没有再次调用供应商。证据 logs/asset-cjpy-browser.log 与 logs/asset-observation-20261021/cjpy-real-summary.json。当前涨幅可由同一快照的 close/yclose 明确计算并标注，交易指标不跨日期补值。
