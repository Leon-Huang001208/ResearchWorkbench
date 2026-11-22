# 今日发现 Implementation Plan

> **For agentic workers:** 在本轮已确认设计和受管隔离分支内按以下依赖实现；后端、跟踪、原生UI分别由具名worker负责，root集成、验证和交付。不再请求已确认的执行方式。

**Goal:** 在研究情报增加已确认的今日发现界面，接现有真实公开情报、冻结资料、手动研究和独立开启的持续跟踪。

**Architecture:** 浏览器仍使用原生Research Web UI；Host沿固定Intel GET取得真实资料，在当前账户Store/DataHub不可变快照中保存版本与原件。手动研究及跟踪均经唯一DSH和原Host质量检查；跟踪复用已有Automation/APScheduler，通过受限adapter与每用户backend生命周期接入，不开放通用管理权限。

**Tech Stack:** 既有Python/FastAPI/httpx/Store/DataHub、JavaScript ES modules、现有Automation/APScheduler；不新增依赖、数据库、第二执行或调度引擎。

## 已冻结的产品与权限合同

- 入口`#/intel/discovery`，沿用已确认v0默认布局、RWB导航/品牌/阅读主题；所有旧栏目保持。
- 页面打开/筛选/刷新只读真实资料，不创建会话、不调用模型。来源失败、空结果、上游陈旧、未知时间和第三方解读错误独立显示，不用样例兜底。
- 选材以Host保存的feed/material标识为准；不接受浏览器自报正文、来源、哈希或任意URL。
- 手动研究先prepare冻结，再明确execute。UUID/请求语义绑定；创建或提交结果未知只核对原身份，不新建/自动重发。
- FinGPT与Claw discovery研究均由受信session/context调用原prepare_contract；不改quality判据、不用执行完成代替验收。
- 跟踪先保存disabled任务，单独enable；固定数据与工具范围、现有模型连接、无MCP或外部投递。仅本账户本模块任务可查看/开启/暂停。
- 周期先读真实资料计算指纹；没有新资料不调用模型。未知/中断保留原attempt/reference，同一资料不自动再提交。质量未通过保留incomplete/invalid等。
- tenant通用Hot/Automation/后台操作接口继续拒绝；既有scheduler在受限资格下只恢复本模块任务。已注册账户重启恢复遵守原RuntimePool容量，容量不足显示deferred，不驱逐活跃实例。
- 本轮验证只用离线fixture、临时隔离账户、公开无凭据有界GET；不启用生产任务、不运行真实模型、不部署常驻。

## Task 1: 真实资料、版本与手动研究

**Ownership:** discovery source/handoff worker。
**Files:** `app/research_web/discovery/{models,sources,handoff,service}.py`，`store.py` additive reserve，`datahub/snapshots.py` additive publication，`tests/research_web/test_discovery.py`。

- [x] 先补有界真实Intel响应、stale/empty/error、未知日期、摘要/原件身份和恶意选材反例。
- [x] 实现有界账户内feed缓存与固定来源，构造真实事件资料包；研究模板问题不伪装成已验证事实。
- [x] 先验证选材版本，再冻结真实event/articles原件与manifest，复用DataHub文件/哈希安全底座。
- [x] 持久预分配session/请求阶段后创建原DSH会话；恢复核对同ID/cwd。未知不再create。
- [x] 实现`prepare/get_handoff/execute/trusted_context`，send沿原幂等键、要求、截止时点与质量合同。

目标命令：`python -m pytest tests/research_web/test_discovery.py --confcutdir=tests/research_web`；失败必须先定位，不能删负例或弱化哈希/未知门。

## Task 2: 受限跟踪与生命周期

**Ownership:** tracking worker。
**Files:** `discovery/tracking.py`、`automation/service.py`、`multiuser/runtime.py`及必要gateway启动钩子；`test_discovery_tracking.py`和近处automation/multiuser回归。

- [x] 补disabled保存、同键参数冲突、独立enable、CAS/失败回滚、外部/跨任务权限拒绝测试。
- [x] 仅从Host冻结主题、当前模型/profile和固定安全工具构造Automation研究定义，不接任意target/MCP/delivery。
- [x] executor先去重指纹/持久attempt，再复用Task1交接与原DSH/monitor；质量与执行分开投影。
- [x] 既有Automation可选eligibility/resume回调缺省保持原行为；tenant下每个恢复、tick、arm、run、enable入口限定owned tracking。
- [x] 原RuntimePool启动恢复仅已注册enabled owner；原容量、所有权、忙/未知边界保留。

目标命令：`python -m pytest tests/research_web/test_discovery_tracking.py tests/research_web/test_automation_service.py tests/research_web/test_automation_research_task.py tests/research_web/test_multiuser_runtime.py --confcutdir=tests/research_web`。

## Task 3: 原生UI接线

**Ownership:** UI worker。
**Files:** `ui/discovery.mjs/css`、`core.mjs`、`app.mjs`、`intel.mjs`、`index.html`；`research_web_discovery.test.mjs`及旧route/UI回归。

- [x] load只GET，取消/迟到响应受route generation限制；无真实数据时不展示v0 fixtures。
- [x] 复用v0主题/期限/证据/反方/条件/履历，提供未知时点与来源状态，绑定实际资料版本。
- [x] prepare展示实际冻结材料，execute明确手动；unknown保留UUID并只读核对，accepted进入既有会话。
- [x] 跟踪save/enable/disable分离，显示scheduler/运行/质量/来源状态；不把保存或执行完成显示为正式接受。
- [x] 保留IME组合、大小写筛选、键盘/焦点、明暗与窄屏。

目标命令：`node --test tests/javascript/research_web_discovery.test.mjs tests/javascript/research_web_intel.test.mjs tests/javascript/research_web_ui.test.mjs`；浏览器使用离线真实Host fixture，并另对公开来源零模型取证。

## Task 4: Host集成、文档、安装和完整验收

**Ownership:** root。
**Files:** `discovery/routes.py`、`main.py`、`service.py`，近处quality/tenant/API测试；模块文档、架构/开发图谱、API/数据/安全/UI/安装说明、原Checks定点清单及Mac静态安装清单。

- [ ] 严格API body、操作header与账户backend归属；不放开通用tenant路径。
- [ ] 装配DiscoveryService/Tracking、受限scheduler与trusted context；原prepare_contract/quality oracle不变。
- [ ] 按全部changed set运行Router；按输出闭包顺序做本地门、独立Python/JS/安全评审、原通用仓库门与同候选Mac干净安装。
- [ ] 新Python文件更新py index、模块说明及.ai任务报告；架构图按真实新增资料边/生命周期更新并重画，不声称无结构变化。
- [ ] 核对requirements/web.in、web.lock、setup_web.py、安装文档与bootstrap。无新依赖的兼容性仍由Mac干净安装证明。

## Task 5: 受管交付

- [ ] root按Git安全入口提交/prepare；重新验证完整集成候选并独立评审。
- [ ] 每次push/merge前核对actions-budget、当前visibility与quota。原必需CI、最新基线和讨论完成后依持续授权合并。
- [ ] 常驻更新、真实付费/模型验证与他平台任务分别保持NOT_RUN，不在本任务中虚报。
- [ ] 证据归档、受管资源收尾与Git安全清理；v0旧工作区/预览服务保留为本聊天既有审阅资源，不强删未归并/未登记对象。

验收计划与回执由实际changed-set Router生成，本文件不削减任何选中的必需门。Windows/Linux真机及同平台产品CI交对应设备，缺证据保留真实状态。
