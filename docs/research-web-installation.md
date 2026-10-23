# Research Web Native / Docker 安装与运行

华安 v2 组合产品56709a8d继续复用既有venv与7c631d4f锁，无新包或凭据配置；前版仍5343e18d。原三公开安装入口及同候选Mac干净安装门保留，旧v1/PR209成功不能替代新操作员CI或实际Office验收。

华安固定Native升级模式只接受前版5343e18d及包含已合并产品988046d的已审目标，沿原安装清单与7c631d4f锁复用当前venv；不安装新依赖或接收新凭据。配置源码仍须原三CI与同候选Mac干净安装，实际切换另取明确授权，之后才验证原生Excel和Word；SDK存在与厂商可调用不混为一谈。

## 今日发现安装兼容（2026-10-23）

本轮复用现有httpx/FastAPI/Pydantic/Automation/DSH，无新Python或Node包；已核对requirements/web.in、requirements/web.lock、scripts/setup_web.py，无需改变依赖或安装器。三公开入口仍从干净checkout安装；原Mac Bootstrap同一步下载并逐字节核验discovery.mjs/css，不增加job/runner/timeout或他平台dispatch。私有账号通用Automation保持0，宿主仅给窄跟踪注入RWB_DISCOVERY_TRACKING_ENABLED=1；只有独立启用且owner后端存活的计划才由原调度器执行，容量延期不保证准点。安装成功不等于来源、真实模型质量或生产计划已验收，详见[今日发现](research-web-discovery.md)。

SPDR 四项快照使用现有 httpx 和 Python 标准库；已核对 requirements/web.in、web.lock、scripts/setup_web.py、
setup-web.sh、setup-web.cmd 和 Bootstrap，均无需为此新增依赖或安装步骤。没有新配置、账号或秘密入口，
Doctor 既有来源/仓库状态合同保持。同候选 macos-14 干净安装、固定 DSH、3081/8088 与 Doctor 仍须实际通过。

2026-10-23：终端固定Native部署复用现有`apply-market-terminal`事务，仅接受冻结前版和产品候选。当前产品检查点尚待PR201合入后由主任务固定为最终PAYLOAD，不能将预检检查点当作可部署版本。固定目标web.lock身份不变，不安装新包；安装清单同步／恢复沿原受管事务。最终组合仍须同候选macos-14干净安装与原两项仓库门，实际部署另证，详见[部署合同](research-web-gateway-upgrade.md#全市场终端固定部署2026-10-23)。

全市场终端v2不新增Python/Node依赖或数据库迁移；原setup-web.sh/setup-web.cmd/python scripts/setup_web.py干净安装合同保持。新的market-terminal.mjs作为同源静态模块加入既有Mac安装HTTP核验；金元普通客户端未认证官方持仓接口，安装成功不等于已接通券商。
管理员Docker构建器登记与实际资源不一致时，使用`rwb-docker builder-reconcile`只读预览，审查当前Engine ID、endpoint及预算后以预览指纹显式恢复。该命令不替代公开Web安装三入口，不装Python依赖、不重置Docker、不切换Native常驻服务。完整故障边界见[Docker合同](research-web-docker.md)。

2026-10-23市场限价/昨日成交额/资金历史迭代不新增项目依赖，一键安装三入口、固定DSH与Doctor合同保持，最终同候选Mac干净安装仍必需。apply-market-history复用已批准主线锁文件7c631d4f及原baostock/psycopg版本，不安装或配置数据库；正式部署前实际核验现有包与pip check，不能只更新清单。用户允许的隔离测试依赖安装只影响任务.venv，不改变常驻环境。
华安 Excel 先行复用已声明的 xlwings/openpyxl，不新增 SDK、安装依赖或凭据接收面。仅有已加载 Wind 的本机 Excel 才可真实采集；Mac 新独立进程心跳通过不足以证明历史函数可用。三个安装入口、固定 DSH、Mac 干净安装/健康/Doctor 门继续保留，未执行 CI/Office/跨平台不得写通过。

## 资产静态资源补充（2026-10-23）

本轮不新增或安装依赖；`requirements/web.in`、`web.lock` 与 `scripts/setup_web.py` 保持不变，原三个公开安装入口继续适用。新增 `asset-layout.css`、`asset-format.mjs`、`asset-chips.mjs`、`asset-chip-panel.mjs` 随原UI目录打包；现有macOS Bootstrap同一步HTTP逐字节核对这四份资源及原固定图表库/许可证。CI没有厂商凭据时仍只显示CJPY已安装待配置。本机真实供应商预检和浏览器证据独立于CI；同候选Mac干净安装、固定DSH、3081/8088与Doctor仍是门。


当前用户已批准PR188／v5组合验收后一起部署已合并锁定baostock0.9.4／psycopg3.3.6；数据库不启用／不迁移、外盘不改，不新增数据库服务或连接配置。v5当前PAYLOAD为完整产品88ef3817、PREVIOUS仍51f09；依赖变化来自PR188已审锁文件，原profile及一行读取修复自身不引入任意依赖。旧a114候选三CI全PASS不能代替新组合的原三CI／同候选Mac干净安装，本轮文档不执行包安装或部署。

资产v5索引预检修复（2026-10-22）只修原操作员的读取绑定：业务index复用既有64 MiB安全读取，部署元数据保持1 MB，旧profile不变。requirements/web.in、web.lock、setup_web.py及Mac Bootstrap无需改变依赖或安装流程；三个一键入口和原同候选Mac干净安装／固定DSH／3081／8088／Doctor门保留。原8.67 MB索引停机前拒绝与PR187 Constraints失败不写成安装或部署成功，修补候选须重新通过原三CI；不裁剪账号索引、不安装包或处理凭据。

2026-10-22资产交互v5使用既有macOS Native操作员，固定旧51f09与PR185产品9bc4，入口`apply-assets-v5`；不新增安装参数、依赖、凭据接收面或Doctor能力。已核对requirements/web.in、requirements/web.lock、scripts/setup_web.py、本页及research-web-bootstrap.yml，依赖／安装器／workflow字节均无需改动。原setup-web.sh、setup-web.cmd、python scripts/setup_web.py三入口及同候选macos-14干净安装、固定DSH、3081／8088和Doctor门保留；产品旧CI与本机installed环境不认证v5最终候选安装通过。实际切换及固定51f09恢复见[部署合同](research-web-gateway-upgrade.md#资产交互与数据-v5-2026-10-22)。

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 该封闭部署事务本身不新增服务、HTTP、持久格式或依赖；它沿用当时已审的图与 API Atlas，不要求重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

2026-10-22 资产交互与结构化数据迭代继续使用现有CJPY 0.5.2、Python锁、固定DSH及本地ECharts／Chart.js。`asset_directory.py`、`providers_cjpy_assets.py`与资产搜索静态模块随既有Web包安装，不新增Python／Node依赖、系统配置或秘密接收面。已核对 `requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py`、本安装文档和 `.github/workflows/research-web-bootstrap.yml`；requirements与安装器无须新增依赖；Bootstrap仅在原静态下载／逐字节比较两处名单追加asset-search.mjs，现覆盖16项资产，不加job／runner／条件。此结论的安装兼容性仍待最终同候选 `macos-14` 干净checkout、固定DSH构建、3081／8088健康和 `rwb web doctor --json` 证明；本机已有包不能算安装PASS。原 `./setup-web.sh`、`setup-web.cmd`、`python scripts/setup_web.py` 三入口与所有平台门保留。

目录只读取当前账号已配置的天软连接，首次打开可能显示加载／未授权，24小时同授权旧缓存可继续显示并标过期；来源配置变化不复用旧目录。不复制开发账号凭据、不自动配置厂商或调用模型。新Provider只声明本轮封闭A股能力；Windows／Linux原生、Docker及常驻部署仍分别记录实际证据，源码和本机预检不自动更新原常驻服务。协议及文件见[资产目录合同](research-web-datahub.md#资产目录与结构化区块)。

## 可选研究仓与只读 Doctor

研究仓是显式配置的可选能力；安装驱动、保存配置及启用标记都不能证明数据库连通、schema权限或数据完整。`rwb web doctor --json` 的 `research_warehouse` 只检查当前实例的 `warehouse.json` 形状、私有目录/文件权限与 `psycopg` 模块可发现状态，不连接PostgreSQL、不读凭据、不调用厂商，也不创建或修改配置。该字段不输出host、数据库名、用户名、数据根、profile ID或owner。

未配置显示 `state=unconfigured`，不阻断整体Doctor。有效配置显示 `state=configured` 和真实 `enabled` 标记；两者都保持 `connectivity=unknown`、`readiness=not_verified`。格式、权限、链接或内嵌秘密字段异常显示 `state=invalid`；驱动缺失单独显示 `driver=missing`。真实数据库可用性必须在UI中显式验证，Doctor不会把旧启用标记或配置存在当成已通过。Windows ACL和其他平台实机验证仍按各平台任务独立记录。

研究仓基座新增锁定 `psycopg[binary]` 3.3.6 与 `baostock` 0.9.4，用户仅授权本任务隔离环境安装及有界免费验证。公开安装器仍从 `requirements/web.lock` 的哈希集合安装，`scripts/setup_web.py` 无额外全局依赖或服务安装步骤。驱动安装不创建业务库，不启用数据采集，不迁移原件；正式库配置/权限和部署另行确认。`setup-web.sh`、`setup-web.cmd`、`python scripts/setup_web.py` 与既有 macOS Bootstrap 干净安装/固定DSH/3081/8088/Doctor门保留，尚待本候选CI证明兼容。外盘ExFAT且无独立备份，不配置为活动数据库数据根。


2026-10-22 插件基座复用既有 Python/Node 依赖与固定 DSH，公开三安装入口、requirements/web.in/web.lock、scripts/setup_web.py、Bootstrap 工作流保持。管理员从能力中心导入固定 ZIP，核对摘要/文件/精确权限后审核；导入不执行脚本或复制 Codex/Claude 凭据。macOS Hook 仅在 Seatbelt 可用时启用，其他平台显示受限。macOS 受管本地 MCP 仅支持经过显式 offline-sandbox 权限和实际 runtime/安装树/schema 摘要审核的离线 Python；安装包只读、独立 scratch 可写，禁止网络、子进程与供应商凭据。npm/Node 和非 macOS 本地执行保持拒绝，固定远程端点保留原生审批流程；Doctor 的 mcp_managed_local_sandbox 仅报告平台入口且 acceptance 保持 NOT_RUN；详情见[插件合同](research-web-plugins.md)。最终候选仍须同候选 macos-14 干净安装、固定 DSH、3081/8088 与 Doctor，当前本地夹具不替代此门。

2026-10-22 v4部署只复用现有Native操作员及生产venv，固定旧5495和PR180产品`9b436613aad9136f4959c992c89dd72fc7354ed5`。公开三安装入口、requirements/web.in/web.lock、scripts/setup_web.py与原Mac Bootstrap合同保持，不增依赖/流程。产品Mac39730452006实际checkout654fa6、581秒，干净安装/固定DSH/3081/8088/doctor及15项静态资源通过；v4工具仍须自身最终同候选CI/安装与部署证据，不能复用产品通过代替。旧v3已正式恢复5495并保全，旧v1/v2/v3恢复及controller/evidence字节不变，见[部署合同](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

2026-10-22 Wind产品PR177已合并，常驻切换单独使用`reviewed-asset-observation-v3`/`apply-assets-v3`：旧主实例/网关必须精确5495，产品必须精确a0ff3ae2；最终操作员候选仍需原三CI及同候选macOS干净安装证据。公开安装三入口、锁定依赖、固定DSH和生产venv保持，不新增依赖、厂商权限或系统配置。用户已授权本轮常驻部署，root在验收后按原锁/空闲/全账号索引保全事务执行；文档或产品CI不等于已切换。旧v1/v2恢复、controller/evidence字节保持，见[部署合同](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

2026-10-22 Wind工作区增加Host内历史任务、兼容Store键与账号图表偏好，继续使用现有CJPY 0.5.2、ECharts 5.5.0、Chart.js 4.4.7及唯一DSH；没有新依赖、安装参数或秘密接收面。公开三安装入口、`requirements/web.in`/`web.lock`、`scripts/setup_web.py`与Bootstrap均按现有合同核对；未修改这些文件的兼容性仍必须由同候选macos-14干净安装、固定DSH构建、3081/8088及doctor证明。历史取数/复权只在已授权来源可用后执行，旧观察与研究材料不迁移；5495是该历史迭代记录的部署基线，本轮实际版本与切换以独立受管部署证据为准，开发态测试不表示已部署。详见[批准计划](plans/2026-10-22-wind-asset-workspace.md)。

全市场概览使用既有固定 `httpx`／AKShare 依赖与产品静态资源，不新增包、厂商配置或秘密。公开安装器必须包含 market Python模块、JS和CSS；三安装入口、requirements锁与固定DSH合同保持，仍须同候选macOS Bootstrap核验干净安装、3081/8088健康及Doctor。公开行情实际覆盖另作本地验证，CI夹具不证明当日源可用；常驻服务不由源码合并自动切换。

资产摘要布局与图表主题迭代只修改既有 Web 静态模块：紧凑交易／估值、来源纯投影、折叠状态及透明图表；继续使用已批准本地 ECharts 5.5.0／Chart.js 4.4.7，没有新 Python／Node 依赖、厂商 SDK、设置、秘密或数据库迁移。公开三入口、`requirements/web.in`／`web.lock`、`scripts/setup_web.py` 与 Bootstrap 工作流保持既有合同；最终候选仍须本地 macOS 验证及同候选 `macos-14` 干净安装、固定 DSH 构建、3081／8088 健康和 Doctor 证据。源码合并与浏览器结果不等于常驻更新；常驻切换须在产品版本冻结后另行交付绑定实际 previous 与精确 payload 的正式版本化封闭 profile，既有部署 profile 不自动兼容本轮资产摘要。

macOS显式资产部署的CI日志复核使用120秒有界下载，普通资格命令仍30秒；读取器完整SHA256由已审操作员绑定。无需新依赖或安装参数，原干净安装、固定DSH、Doctor与恢复门保持，详见[部署合同](research-web-gateway-upgrade.md)。

资产观察 AF 连续指标区随既有 Web 包安装，新增已独立授权的本地静态 ECharts 5.5.0 与 Chart.js 4.4.7，固定版本、许可及SHA-256，不依赖CDN或开发者全局包；无新Python包、厂商SDK、秘密或模型权限。公开 `./setup-web.sh`、`setup-web.cmd` 和 `python scripts/setup_web.py`、`requirements/web.in`／`web.lock`、固定DSH及原Bootstrap合同保持。交付须核对本地静态库、wheel及干净安装物逐字节一致，并由最终候选 `macos-14` 的3081／8088健康与Doctor证明安装兼容；核对文件无须修改的结论也须由安装CI验证。本机已有环境与浏览器夹具不能替代此门，真实CJPY冷启动首次查询、逐区刷新及Wind可用性另留证据。

显式联合升级保留独立的常驻发布 clone；仅构建源码使用受审 source 的 common directory，两发布角色分别绑定原 Git 目录/inode 和同一 GitHub origin。目标对象缺失在停机前拒绝，不修改既有安装布局或凭据。

现有常驻的模型服务商后端更新使用[显式联合升级](research-web-gateway-upgrade.md#模型服务商联合升级)，须受审精确 SHA、Mac 干净安装证据、真实空闲及恢复准备；不替换原控制器、不安装新依赖、不迁移凭据/会话。公开安装入口和依赖锁保持。

网关冻结恢复任务显式提供既有系统/Homebrew工具PATH，安装前核验Git LFS；本轮不安装新依赖、不修改公开安装入口或全局环境。干净Mac Bootstrap仍是必需门。

需保留旧主实例版本时，显式 `apply-ui --preserve-primary` 使用v3恢复合同。三段受限差异、原锁/空闲/排空/保全均通过才更新网关；公开安装入口和依赖锁不变，仍须同候选Mac干净安装CI。

已验收UI的网关更新使用[显式apply-ui事务](research-web-gateway-upgrade.md#已验收界面的显式更新)：工具和产品各自核对资格，主实例不重装；恢复artifact有独立内容身份，不替换旧控制器。没有新依赖、凭据、数据库迁移或默认安装步骤，原锁与Mac Bootstrap安装/健康门保持。

自由分析/中文报告修复沿用已锁定的stdlib、python-docx和ReportLab，无新增依赖、设置、凭据或迁移。公开安装入口、requirements/web.in/web.lock、setup_web.py保持；同候选macOS Bootstrap验证干净安装与固定DSH/健康。包内原四个SDK文件及字体白名单不扩大，旧会话和模型配置原位保留。

网关安全更新在SIGTERM后等待PID真正消失，退出未回收或签名变化都不触发追加信号。完整保全journal专用读取上限16 MB，首次信号前检查实际序列化字节并保留4096字节阶段余量；通用配置读取上限保持1 MB。Mac Bootstrap用临时子进程和临时大journal验证这两条合同。

Mac网关更新通过内核proc_pidpath核对实际Python映像，兼容Homebrew启动器exec到Python.app；argv0只接受该受管解释器的三个精确路径，完整参数、PID起始时间及8089 listener继续核对。Mac Bootstrap在原环境校验步骤执行原生探针，不增加依赖或安装流程。

附接网关与主实例版本不一致时，使用显式[空私有池安全升级](research-web-gateway-upgrade.md)；不能只替换 binding 或放宽自动白名单。主实例继续运行，活动/未知延后，失败恢复网关的匹配绑定与旧源码。公开安装依赖、固定 DSH 和安装入口不变，兼容性由同候选 macOS Bootstrap 验证。

本轮网页日期、数字声明与历史/URL 修复没有新增依赖、设置、凭据或迁移；Web 锁、setup_web.py 和固定 DSH 保持，干净安装仍由同候选 macOS Bootstrap 核对。其他平台原生验收保持独立。

本轮仅统一业务报告提示和原一次补查路径，现有会话、模型设置、依赖锁、安装入口与固定 DSH 均保持；由最终同候选 Mac Bootstrap 证明干净安装兼容，不安装新依赖。

本轮数字与最终报告链接修复不增加依赖、凭据、设置或迁移；requirements/web.in、web.lock、setup_web.py和固定DSH不变。同候选macOS Bootstrap仍验证干净安装与健康；未执行的其他平台层保留NOT_RUN。

旧会话 SDK 兼容依赖包内既有三个报告 Python 文件与 Noto 字体，均随现有 wheel/资源合同交付；没有新依赖、设置或迁移。Host 沙箱固定只读这些文件，既有会话目录不覆盖；最终候选仍须 Mac 干净安装与本机 Native 验证。

报告配方使用现有标准库及报告依赖，无新增安装项、用户配置、数据库迁移或模型配置格式。公开三入口和锁文件保持，最终候选仍需 macOS Bootstrap 干净安装证据；现有会话及模型凭据原位保留。

FinGPT隔离比较不新增依赖或生产配置；测试模块随既有wheel携带但无自动启动入口。Lite设置仅写本次case的Keychain账户，Flash仅复用受管只读凭据调用；公开setup、锁文件、固定DSH和常驻服务保持。新控制器的打包/安装由同候选macOS Bootstrap验证。

正文取证使用现有 Python 标准库及原私有回调，无新依赖或凭据设置。requirements/web.in、web.lock、setup_web.py 和 Mac Bootstrap 安装流程保持；新增模块须随 wheel 进入干净安装。正文读取与取消、版本回执元数据超出 resident 自动兼容范围，须经精确候选专项复核后在空闲门内切换，不扩大自动白名单或搬迁研究数据。

本次质量修复只使用已具备的Python标准库及既有报告依赖，不新增依赖、数据库schema或模型配置。公开安装入口与requirements/web.in、web.lock、setup_web.py、Bootstrap保持；仍须由本机与最终候选macOS干净安装CI证明兼容，不能依赖开发环境推断。

管理员 stage 停止仍保留容量；已完成任务仅通过 Docker 手册的 release-reservation 精确身份入口释放预留，容器和卷保留。公开安装与凭据初始化合同不变。

用户实例重启后只读验证.control中的DataHub/MCP回环URL并复用原Web端口；没有记录才新分配。已有端口被占用、原址不一致或控制记录异常时明确失败，不改内部token、不接管未知进程。该恢复不需要迁移旧会话、模型配置或原primary实例。

primary 的 index.html、/static 资源及原 /api/research/aihot/ 阅读请求继续使用其已验证旧实例版本；/auth、/account 与账号包装脚本来自新网关。静态响应 no-store，身份来自 Cookie，浏览器不能指定源码根。这样部署登录网关不会隐式切换原资讯后端；不在本任务启动资讯数据库或 worker。

### 显式保留既有常驻实例

已安装的 Mac 可在单独授权部署后，由操作员将唯一 primary 管理员绑定到经过目录身份、安装 SHA、进程归属和实际健康核验的原 Web/DSH。原数据根、模型配置及 Keychain 命名空间原位保留；原监督器继续拥有其生命周期。primary 不能被用户管理界面停用或停止，其他用户仍使用新用户根；原实例占用两个总槽中的一个。此绑定仅限可信的服务器所有者管理员，原个人实例保持原能力，不能绑定普通受邀用户。

独立 `com.research-workbench.multiuser-server` 用户 LaunchAgent 用已审核的精确源码 SHA 执行 `python -m app.research_web.multiuser.resident --root <private-root>`；解释器、Node 与固定 DSH 复用已安装环境，无新依赖。私有 `resident.json` 保存绑定身份及部署 SHA。先验证回环 8089，再持有原 supervisor/admission/lifecycle 锁复查空闲，在路由切换前写 `run/cutover.json`，检查原会话文件与模型配置摘要后，才把既有 Tailscale HTTPS 根代理 8088 改为 8089。该 journal 存在时拒绝业务写入；原实例不停止，不改变自动兼容白名单。失败仅恢复本次拥有的原路由并停用新网关，不覆盖研究数据。安装日志与保全证据仅存本机私有目录。

初始管理员密码可由已授权操作员随机生成并只写入 macOS Keychain，配置只记录服务名/账号引用；不得出现在 argv、环境、日志、报告或聊天中。用户登录后可通过菜单顶部用户名进入账号资料；管理员在“设置 → 用户管理”重置密码，普通用户联系管理员。匿名 `/api/server/health` 只显示网关就绪及 primary 先前核验标记，不探测模型、不反复启动子进程；认证主账号的深度核验采用单飞与三秒缓存。正常退出只回收新用户 pair；登录启动等待原监督器恢复。仅在内核 boot UUID 已变化且旧 owner 完整、账号已知、权限与目录安全时，归档并退休旧控制元数据；同 boot 崩溃及未知归属仍拒绝启动。登录后启动与完整重启实测分别记录，FileVault 与系统登录策略不改变。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](research-web-ai-news.md)。

## 私网邀请制多用户（macOS Native）

独立 `serve --max-instances` 支持1至4个Web/DSH pair，默认仍为2。附接原实例的常驻入口另从私有 `server/resident.json` 读取 `max_additional_instances`（整数1至4，省略仍为1）；它只计额外用户，原primary另占1个实例。因此配置3表示总计4个，配置4表示总计5个，并不代表所有宿主均已验证该最大值。`rwb server doctor --json` 的 `capacity` 只读显示配置的额外及总上限，非法/非私有记录显示invalid；不是硬件或真实模型压力验收。

本次24GiB/12核Mac mini实测3个额外pair约1.06GiB RSS，60个并发列表请求通过，swap未增长，生产选择额外3（加原primary共4）。保留约6GiB工作波动预算及主机余量；RSS是轻量下界，重型研究、长上下文/大量文件及真实模型并发尚未验证。满槽拒绝新实例，不驱逐既有用户；减少配置只在受控重启后生效，仍须先确认无活跃研究，保全数据及模型。没有自动回收或硬性内存配额，额外用户的退出登录也不释放实例槽。

此模式是显式选择的独立服务器入口：Mac mini 保存所有账号的研究数据；用户通过浏览器登录，管理员在“设置 → 用户管理”创建/停用用户、重置密码和停止用户实例。没有开放注册。默认原单用户入口、个人数据、resident 与 Docker 实例均不转换为服务器；不自动部署 Tailscale、迁移数据或复制原模型密钥。

AI资讯由网关使用 `server_root/shared/ai-news` 全局库：已登录成员阅读正文/专题/图片/RSS，status/control仅管理员可用。共享库不放入用户DSH根；逐用户tenant后端封禁全局AI路径，资讯请求不启动研究实例。默认未配置不创建目录或数据库、不调用模型；首次共享库初始化与服务启动仍须单独授权，详见[多用户资讯合同](research-web-ai-news.md#私网多用户权限与共享目录)。

先用公开 `./setup-web.sh --runtime native --no-start` 从干净 checkout 安装已有锁定 Web 环境并构建固定 DSH；无新增依赖。随后在有 TTY 的 Mac 终端初始化全新私有服务器根，密码交互输入，不放命令参数或环境变量：

```bash
./rwb server init --username admin
./rwb server doctor --source "$HOME/.research-workbench/dsh-source" --json
./rwb server serve --origin https://mac-mini.tailXXXX.ts.net \
  --source "$HOME/.research-workbench/dsh-source" --node /absolute/path/to/node
```

示例域名必须替换成已获准设备的精确、小写 Tailscale HTTPS origin，不能有路径、查询、尾部斜线或用户信息；`--node` 指向已有、匹配固定 DSH 的 Node 可执行文件。Serve 只监听 `127.0.0.1:8089`；操作员另行明确授权后配置 Tailscale Serve 将该精确私网域名代理到此端口，不使用 Funnel，不覆盖原个人实例代理。测试可显式使用 `--origin http://127.0.0.1:8089`；此时 Cookie 不带 Secure，仅用于本机开发。

所有命令可选 `--root /absolute/private/server-root`，默认为 `~/.research-workbench/server`。`serve` 可选 `--port`（默认 8089）及 `--max-instances 1|2|3|4`（默认 2），不接受多 worker；首次研究才占用实例槽，容量满明确返回 busy，不自动驱逐。管理员在 `/#/settings/users` 的“停止实例”释放槽位，停用账号会撤销登录并停止其受管实例；仅退出登录、关闭页面或重置密码不停止研究。网关前台正常退出会关闭本进程创建的实例；崩溃残留身份未知时失败关闭，需要操作员核查，不能自动终止未知进程。

`./rwb server reset-admin --username admin` 交互重置既有管理员密码并撤销该账号所有登录态；不会创建新的管理员或搬移会话。密码至少 12 字符。`server doctor` 只读检查账号库、源码构建文件及解释器/已有模块，输出 runtime/model `not_checked`；`build_present` 不代表固定 SHA、运行健康、Tailscale、真实研究或模型通过。尚未安装时 help/doctor 仍可用；服务启动只用安装后的 Web Python。

每位用户使用独立模型凭据命名空间，首版只开放官方 DeepSeek，不读取管理员个人密钥、不接受自定义模型目标。服务器 profile 关闭宿主浏览器、Office/Wind、本机连接配置、MCP、Hot、日程/自动化、报告 Workflow 和运维接口；文件式文档仍按用户根操作。私网网关透传研究接口必需的幂等请求头，登录和列表可用不能替代实际提交验收。模型、来源与报告的真实可用性保留独立状态，不因登录成功宣称研究通过。此首版信任同 UID 后端及固定工具实现，不提供恶意同 UID 进程/任意插件的 OS 租户隔离；Windows/Linux 与 Docker 多用户均未接入。安全及数据位置见[安全边界](architecture/research-web/05-security-validation.md#私网邀请制账号与执行边界)和[数据与文件](architecture/research-web/03-data-files.md#服务器账号与用户数据)。

AI资讯文章全文、事件专题和主题分页沿用同一Host与公开安装链；自主库未配置时诚实503，不调用模型或回退外站。可选Node依赖、独立库迁移及采编生命周期按下列合同分别验收；最终候选仍须Mac干净安装CI，常驻更新沿单独授权及现有事务。

AI资讯自主引擎使用已固定上游Node锁文件。公开安装入口安装依赖时使用 `npm ci --ignore-scripts`，不创建数据库、不启用采集、不调用模型。Python产品依赖沿用 requirements/web.in 与 web.lock。Doctor新增可选 ai_news 就绪事实，模型质量始终单列。

首次独立数据库初始化、60份固定迁移、凭据和服务生命周期必须单独授权；`rwb ai-news status --json` 与 `doctor --json` 只读，显式 `setup --authorized` 仅作用于已验证的本机新库。备份、恢复与故障续跑合同见[自主资讯](research-web-ai-news.md)。不复用Hot业务库，不导入线上历史，不自动升级当前常驻服务。Mac干净安装CI仍核对固定DSH、3081/8088与Doctor；Windows/Linux原生保持独立交接。

FinGPT 单引擎融合不新增 npm/Python 产品依赖，不增加供应商环境文件或秘密配置入口；沿用公开安装器、固定 DSH 和既有凭据存储。requirements/web.in、web.lock、setup_web.py 无需修改，兼容性仍须由本地回归与 macOS 干净安装 CI 认证。没有启用或部署新引擎；常驻服务切换需另行明确授权。

会话导航的项目/置顶/排序保存在既有产品数据根的Host索引，FinGPT与Claw分别管理；显示折叠偏好按模式保存于浏览器。不新增依赖或配置步骤，原公开安装入口和固定DSH保持。本轮元数据/API变更仍须独立部署兼容复核，不能自动扩大resident白名单。

正文搜索使用固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73` 的显式部分搜索接口：Host 将 RWB 已创建、未删除且符合当前模式的 ID 范围传给原生层，再与原生列表可见范围取交集。响应必须包含完整范围内的 `unavailableSessionCount`；Web 返回 `unavailable_count` 并在零命中时仍提示部分历史未搜索。旧格式源记录保持不变，不授予恢复执行；I/O、损坏及取消仍失败。未升级的旧接口缺少覆盖信息时明确报错，不假称搜索完整。

## macOS 登录后常驻与自动部署

新版资产页通过独立 `model_provider_upgrade apply-assets-v2` 交付，固定旧主实例／网关 `9bc12355c3b80e4e4459f4c250e13fc2634ed23d` 与 PR175 产品 `93d62be64084a5c92541a4a008216c0b3f56c2f1`。最终操作员须先通过原三项 CI 与独立评审，再从同源码 common directory 的干净目标 checkout、使用原生产 venv 执行；含未跟踪文件的开发目录不能直接用作操作源。原 v4 恢复、空闲与完整业务索引保全继续生效，旧 v1 和模型专项不改。此流程只安装本项目 wheel，无新依赖、配置项、HTTP 字段或迁移；公开安装入口及 `requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py`、Mac Bootstrap 保持兼容并按候选验收。详见[固定版本联合部署](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

资产观察有显式 `model_provider_upgrade apply-assets` 合同，固定 c688 旧版本与已审 PR171 产品，只复用现有生产解释器安装本项目 wheel，不安装新依赖或扩大自动兼容范围。必须先通过最新源码资格、资产/DataHub与原Native/Host/私有池空闲、保全和恢复检查；使用方法见[固定版本联合部署](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

模型服务商联合升级可同时交付 PR168 的五个精确导航 UI blob；其余产品文件仍绑定原模型服务商基线。须通过最新已合并候选的三CI、独立评审与原空闲/保全事务，不使用复制静态目录或临时放宽自动白名单交付界面。范围见[联合升级合同](research-web-gateway-upgrade.md#模型服务商联合升级)。

UI 更新若同时包含显式网关升级工具，可按[受控 UI 候选准备](research-web-gateway-upgrade.md#显式准备主实例-ui-候选)先准备精确新旧 wheel，再由原不可变 resident 执行空闲切换；之后独立更新网关。此专项不扩大自动白名单、不安装新依赖、不改 baseline 或数据根；工具本身的 Git blob 必须与冻结恢复工具一致，主实例和网关均须核对原会话及模型保全。

适用于已安装 Native 的 Mac mini，保留 FileVault。开机解锁并登录安装用户后，
LaunchAgent 自动启动/恢复 Web 8088 与 DSH 3081，每60秒只读检查 GitHub master。
关浏览器或聊天不影响服务；关机/休眠/断网期间不能远程访问。不修改 Tailscale Serve。

在已验证、已部署且带 resident 准入的固定生产 checkout 中显式安装（参数换成本机路径与域名）：

```bash
./rwb resident install --project /absolute/production-checkout \
  --source-repository /absolute/development-checkout \
  --private-origin https://research.tail123abc.ts.net
./rwb resident status --json
./rwb resident tick
./rwb web doctor --json
```

安装不新增依赖。Node使用现有固定toolchain，GitHub使用现有gh认证；不会保存新token。
私有配置/journal/控制器artifact放在 `~/.research-workbench/resident/`，日志在产品 `logs/resident.log`
（滚动保留）；启动项为 `~/Library/LaunchAgents/com.research-workbench.resident.plist`。
`resident status` 不启动服务；Doctor的resident只读本地状态，不等同登录项/外网/模型验收。

自动候选须为最新master且已有本机受管delivery完成记录、matching独立review、GitHub merged PR，
以及Project Constraints、Research Web Checks、macOS Bootstrap的成功实际checkout与master树相等。
缺Mac CI的迭代保留waiting，需按原交付流程补齐对应候选CI。
先准备新旧wheel，空闲后才持有研究EX栅栏及原lifecycle lease切换；
原生会话含子会话、已接受的排队/运行Automation均阻止切换。保留同一数据根与凭据，固定8088/3081，
不抢未知进程/端口。候选HTTP/私网HTTPS/实际进程revision失败则重装精确旧wheel并恢复旧源码和manifest。
journal同步落盘先于停服务；中断后先恢复旧版本，失败时blocked且新写入继续拒绝。

自动兼容范围采用显式路径清单：静态UI、文档/测试及已登记的无持久化启动变更模块。
依赖锁、DSH、打包/安装器、Store、研究/自动化生命周期、Hot及未分类模块变化暂停为
`resident_compatibility_review_required`，须完成专门升级并刷新基线；不自动安装依赖或执行迁移。
控制器不会自己更新，不能用普通代码更新扩大既有准入。更换生产目录/Node/gh需重新核对身份。

经单独授权的Host元数据专项：先完成源代码交付、独立评审及三CI，从同一受管Git仓库创建最新master的干净工具worktree，再显式执行：

```bash
/absolute/verified-tool-checkout/rwb resident upgrade-host-metadata \
  --expected-previous 02c086b168e62723887c7a778f716f6146595b6d \
  --expected-target EXACT_VERIFIED_MASTER_SHA --json
```

工具代码必须来自精确目标checkout，不能使用dirty开发目录；业务仍只在原固定生产根启动。
该入口不接受force、不扩大自动清单，不支持任意升级或迁移：固定PR122四个Host文件内容，
其余仅允许原静态范围、两份生成文档和已验收专项工具自身。它只读检查现有元数据容器，
保留Claw原项目及所有会话；排队/活动/未知研究延后，候选失败沿原事务恢复旧代码和wheel，
不恢复或回写业务数据。仅目标健康、accepted记录和配置身份复核成功后更新baseline并保存审核记录。
延后时保留已验证候选，原监督器继续原空闲门；成功后可使用同一精确命令补完基线，避免二次重启。
目标master或Host内容变化、隔离候选、遗留事务、未知路径/元数据类型必须停止并报告。


```bash
./rwb resident rollback   # 同样先核对空闲；只回退代码/安装包，不覆盖研究数据
./rwb resident retry      # 显式允许再次尝试已隔离的失败候选
./rwb resident disable    # 停用登录监督；不停止现有Web/DSH或Tailscale
```

首次把旧安装引导到带准入的新版本需操作员安排维护窗口；旧版本没有准入锁，不能把一次空闲快照
当作已关闭并发竞态。真实重启登录、另一设备和付费生成是独立验收，不由启动项加载或健康检查替代。

Claw新增的正文搜索只复用固定DSH已有session.search与现有Python/Node依赖，未改变web.in/web.lock、公开setup入口或DSH pin；原生provider不可用时明确失败，不自动安装或迁移。新的前端模块通过现有UI包数据安装，候选Mac Bootstrap仍须绑定实际提交。

工程交付结束后由原Git安全入口执行资源收尾，规则见Docker手册和AGENT_WORKFLOW：仅删除本任务已登记的再生依赖，并保护应用现有安装、业务数据、凭据、报告和恢复归档。受管构建缓存合计20GiB，临时维护完恢复构建器原资源限制/停止状态，不重启产品服务。本轮没有新增安装依赖、公开setup参数或用户模型配置；干净安装兼容性仍由既有Mac Bootstrap证明。

## 可选：Tailscale 私网 HTTPS 访问（Native）

可从聊天或其他网页直接点击入口链接。浏览器须发送用户触发的顶层文档 GET 导航
（Sec-Fetch-Mode=navigate、Dest=document、User=?1），且 HTTP 路径仅为 `/`；
`/#/fingpt`、`/#/claw` 的片段仍由浏览器路由。缺失/不符的导航元数据、iframe、
跨站 API/资源请求、显式外站或 null Origin 仍拒绝；Host/HTTPS 准入和 CSP 不变。

默认仍只接受回环 Host。已安装并登录 Tailscale 后，由操作员指定本设备的精确 HTTPS
origin（示例域名必须换成 `tailscale status --json` 中本机的 DNSName，去掉结尾点）：

```bash
RESEARCH_WEB_PRIVATE_ORIGIN=https://research.tail123abc.ts.net ./rwb web restart
tailscale serve --bg http://127.0.0.1:8088
./rwb web doctor --json
```

首次启用 Serve/HTTPS 需在 Tailscale 管理页授权。若本机接受的 Web 端口不是 8088，代理目标
使用 `rwb web status` 的实际端口。仅允许单个小写 `<device>.tail<id>.ts.net` HTTPS origin，
不带端口、尾斜线、路径、查询、凭据或通配符；非法配置以 `private_origin_invalid` 拒绝启动。
该变量是启动配置，下一次 start/restart 也需携带，可保存在本机私有启动脚本中；不会自动
修改系统环境、登录项、网络成员或访问策略。Doctor 的 `web_access` 读取运行中 Host，
不从当前 CLI 环境推断已应用。移除变量并重启后恢复回环访问。

客户端必须登录获准的 Tailscale 网络。Serve 保持私网，不启用 Funnel；不要将此 opt-in
视为公网身份认证或多用户隔离。Mac 必须开机联网；休眠、重启及 FileVault 解锁后的恢复
需另验。浏览器或系统代理应绕过此精确私网域名，否则可能发生 TLS 连接失败。
关闭本次入口使用 `tailscale serve --https=443 off`，不停止 RWB。

此能力不新增依赖；已核对 web.in/web.lock、setup_web.py 与 Bootstrap workflow，保留原安装
合同，由候选的干净 macOS Bootstrap CI 验证兼容性。Docker 不在本切片启用此宿主配置。

## 外部来源与兼容模型融合

打包research_helpers新增chinese_font_path，仍复用现有中文字体和Matplotlib，无新产品依赖。
新版任务提示传达真实能力/来源准入；旧会话资源不会被覆盖，字体可从模块绝对__file__兼容定位。
AKShare缓存语义版本升级只失效复用，不删除历史数据；首次新调用重新验证请求口径。

外部来源目录、JSON 模型预设和取数适配器随现有 Web 包安装，无新增产品依赖；
`requirements/web.in`、`requirements/web.lock`、安装器与 Bootstrap 工作流保持原合同。
连接中心新增 ext_ths/ext_daole/ext_tikhub/ext_cicc，凭据只在本实例设置页接收。
目录、已配置和真实取数成功分别显示；Doctor 的健康或依赖安装不证明供应商可调用。
认证入口必须使用 HTTPS；目前道乐目录的 HTTP 入口返回
`credential_transport_blocked`，不会读取或发送其 API Key，不猜测 HTTPS 替代地址。
普通公开入口不自动继承秘密，参考来源不提供取数能力。

兼容模型预设只对已匹配的本地 gateway 展示；其他 endpoint 使用自己的模型目录。
未披露模型容量时使用 32768 的保守上下文压缩预算，可由运行时显式配置覆盖；
该预算不是模型能力认证。兼容传输支持工具流，不自动授予任意 endpoint/model
深入研究或受验证能力准入；既有验证门保持。自动压缩使用已固定 DSH 插件，
不改 DSH pin。安装和 Bootstrap 继续验证实际固定构建与 3081/8088/Doctor。

可在完成既有Hot Node依赖安装后运行node services/hot/scripts/evaluate-corpus.ts离线复核；无新增依赖、数据库或凭据要求。该命令不证明完整安装、Docker镜像或真实模型全关系通过。

事件日期可从研究情报人工纠错配置，或用已有rwb hot event-correct CHANGE.json --reason传times变更；引用当前事件材料版本/非空原文摘录，格式day=YYYY-MM-DD、instant=UTC ISO毫秒，timezone为来源IANA时区。occurred/effective两项必给，null表示未知/撤回；无需改源码、依赖或迁移。新镜像/干净Mac安装CI仍需匹配当前候选。

升级来源界面后，Doctor的checks.source_catalog仅核对目录控制列权限，ready不代表模型调用或完整历史覆盖。setup_required时停止Hot并执行原setup更新权限，再启动。来源页可设置默认间隔0或60–86400秒，并显式目录接入；无新依赖/迁移。新静态模块hot-sources.mjs随现有ui包数据安装，当前候选干净Mac安装CI与新镜像仍须取得。

接续旧冻结来源时，先停止Hot并运行`rwb hot setup`重授controller的sources.config列权限（schema仍20、无依赖改变），再启动。`rwb hot source-configure fed --expected-revision 4 --use-catalog --reason "恢复官方持续采集"`明确按固定DataHub目录激活；只能绑定已有同运营主体公开源，不接受URL。配置字段与旧材料保留，预算不变。普通worker没有config写权限；源码新字段尚需当前安装CI和新镜像验证。

已有停止stage的pre-AES容器与已初始化model_key账本可经显式不可变镜像替换升级：严格核对旧容器归属及停止态，仅退休没有模型环境的旧四挂载容器，下一次up挂载既有只读密钥卷。普通操作不接受缺挂载；不初始化新密钥、不删除五卷、不更新prod，无新增依赖。

Hot非秘密配置可指定`model.materialIds`（最多20个唯一材料UUID）进行有界处理；省略或空数组处理普通积压。先停止Hot、修改既有配置、再启动，凭据仍来自该模式的受控桥接；字段不创建预算、不提高限额、不增加依赖或迁移。重启保留未选择任务。当前真实Native组件已处理近期AI材料并生成两频道周期产物，schema20联合恢复已验证；最终完整镜像及同候选干净Mac安装仍须独立通过。

Hot升级关注和周期简报需要先停止原worker，再通过既有 rwb hot setup 的迁移所有者升级schema19/20并重授最小角色权限，最后启动。公开安装依赖锁与安装入口未新增包；干净Mac安装CI须绑定最终候选。新计划保存为停用，启用为单独明确动作；默认首次时间在未来，频率/窗口/事件上限/显示时区通过页面配置。Doctor状态和周期运行记录分别核对，不用配置成功代替实际冻结简报。

Hot研究页面动作只使用随现有静态UI安装的原生模块与已有API，不新增依赖或迁移。候选341000f7的Mac公开安装CI已通过；随后UI增量仍须绑定自己的检查，不能借旧CI认证新增源码。Docker组件24060ee3与最终整镜像341000f7的证据分开。

可选 Hot 服务要求 Node 24.11+，Mac 安装 CI 使用与当前 Docker 镜像一致的 Node
24.19.0，并在公开安装器运行后直接导入 Hot 的三个生产依赖、核验 Node 版本。
该步骤不连接 PG 或模型；数据库配置、真实采集和模式切换仍须各自实机证据。

Hot 的生产 Node 依赖现在由 Native 一键安装器按组件锁文件安装，使用受管 Node/npm，
执行 `npm ci --omit=dev --ignore-scripts --no-audit --no-fund`。Docker 镜像也包含相同锁定
依赖、Hot 源码和迁移文件；PostgreSQL 仍是显式配置的外部数据库。
容器内 Hot 配置/运行日志写入私有数据目录的 `hot/logs/`，不写只读源码根。
Docker 不装配 Native 模型凭据，模型不可用状态保留为 `blocked_model`。
这些安装契约变更仍需干净 Mac 安装、真实容器运行及候选 macOS CI 分层验收。

所选研究资料可随暂停的 PG 备份联合封存：`rwb hot backup --include-session <UUID>`。
联合 `restore` 需传 `--research-data-home <全新目录>`；恢复前核验双方清单、签名与哈希，
恢复后保持暂停，不恢复凭据或 Native 执行历史。PG 已恢复但文件复制中断时，可用
`restore-research-snapshots` 重试同一封存档，避免再次恢复 PG。详见 Hot 组件 README。

Hot/model启用后重启Web Runtime以生成本实例官方provider零重试配置；配置本身不授予
预算。修改后实际重启与模型研究仍需验收。model-terminate现在可明确取消DB证明未发送的
reserved预留；已发送/未知仍不退款，先停止Hot并保留相同操作UUID恢复未知管理回执。

Hot流插件随已有app/runtime安装，无新包或迁移；发送需要当前价目、原授权及零重试。
正常official默认5次重试目前被桥拒绝，专用策略装配待验。离线SDK通过不认证干净安装或Mac CI。

2026-10-13 阅读界面新增本仓原生 `hot-reader.mjs/css` 静态资源，沿已有FastAPI/static与
Web包数据路径安装，没有新增React/Tailwind运行依赖或CDN。Native/Docker的完整安装兼容性
仍须由候选Mac Bootstrap证明；源码/隔离预览不替代干净安装。原Hot数据库未因界面迭代迁移。

Hot Native 模型上下文与 Web 共用 `runtimes/research_web.json` 的固定 DSH，装配新版
`llm-deepseek-api-key` 官方路由；旧提交与修改过的 tracked checkout 被拒绝。日期价目
仍须当前有效并绑定已授权累计 scope。migration17 的研究预算/调用映射只在停机迁移
后启用；当前原验收库仍 schema15/paused，新 schema 的随机测试不认证干净安装或正式研究。

本轮预算适配不改变依赖、公开安装入口或固定 DSH；常规安装不初始化/激活预算。显式候选验收只接入已认证的受管 AES 模型实例，Fernet/Native 正常安装不受影响。旧政策过期，新的真实窗口需另外授权及政策复核。

ETF工程模拟使用现有Pydantic/FastAPI及stdlib SQLite，无新增Python/Node产品依赖或安装参数。
首次显式模拟在所属产品根创建私有 `portfolio-decisions/paper.sqlite3`；工程输入不会配置真实数据来源、
凭据或启用算法。数据/能力缺口由模拟页readiness显示，不能把Doctor的服务健康视作策略可运行。
本切片的干净macOS安装CI与Docker开发/镜像验收尚待执行，现有环境聚焦通过不替代这些门。

Claw 回答工具卡、保存回执、显式格式助手与会话工具目录收窄均复用固定 DSH 和现有依赖；web.in/web.lock、setup_web.py 与 Bootstrap workflow 未增加依赖或安装参数。Native 候选已通过公开安装器 repair/no-start 更新，必须使用安装器选择的受管 Node 启动。模式记录的共享祖先目录允许无关同级活动，私有 install 父目录与记录仍严格验证；Windows/Linux 验收由对应设备执行。

Claw 项目与日程入口使用既有 Web/DSH 依赖，无新增产品包或安装步骤。旧数据根可直接读取，缺少 project_id 的 Claw 会话归入默认“我的研究”，不移动文件。
Claw 接入固定 DSH 已存在的 ask_user_question 插件，无新增 Python/Node 依赖，公开安装入口、web.in/web.lock/setup_web.py/Bootstrap workflow 保持原锁。
Automation 被显式关闭时，聊天日程草稿也不可用；提出草稿不等于保存或启用。直接 research_task 无需 Skill；旧目标仍需实际能力版本，数据/模型/工具的可调用性继续由现有设置与 Doctor 分层诊断。

固定 Native/Docker 启动 overlay 的 DeepSeek 单次输出上限为 16384 tokens；不修改模型凭据、DSH pin 或锁定依赖。截断仍是 incomplete，文件验收必须核对原生完成事件及实际非空产物。

## 中文 PDF 依赖与验收

Web 锁新增 ReportLab（reportlab>=4.5,<5），使用原 Python3.12 universal/哈希解析流程；其余锁定依赖保持。resources/fonts 包含可嵌入的 Noto Sans SC 静态中文字体、OFL 许可证和固定 Google Fonts 来源摘要。产品 PDF 不要求宿主 Office、CMake 或 Node 开发头文件；后两者是固定 DSH 原生构建的工具链前提。

安装器继续通过完整锁与项目包安装校验依赖。验收须实际生成中文 PDF、重开提取文字并渲染关键页，源码/单元测试不替代干净安装与 Mac CI。任务内测试环境不发布，不读取其他任务模型密钥。


2026-10-12 起，24GB Mac mini 是 Docker 主开发与常驻节点，MacBook Pro 是远程入口。
新的纯 Docker 安装和显式实例管理使用 [Docker 开发与部署手册](research-web-docker.md)：
`./setup-web.sh --runtime docker --environment stage --instance local --web-port 18088`，
随后 `./rwb docker stage local doctor`。宿主只需 shell、Docker CLI/Engine 和 buildx，
不探测宿主 Python/Node。Native 无参数入口、Windows cmd 及
`python scripts/setup_web.py --runtime docker` 的 legacy 合同保留；它们不管理新实例账本。

## Docker 资源命名与收尾

新构建使用 `research-workbench:dev-<短提交号>-<构建号>`，镜像标签保存完整提交号与构建身份。
源码归档或宿主没有 Git 时明确使用 `unknown` 并记录警告，不新增宿主 Git 依赖或伪造提交号。
新 Compose 项目使用 `rwb-dev-<安装短ID>`；既有安装继续使用其原 Compose 名称。
项目、用途、安装或任务身份、`persistent`/`temporary` 属性通过标签记录，名称不充当删除授权。
安装替换前保存 `install/docker-previous-manifest.json`；发布失败恢复原回滚记录。
有效安装及上一接受版本均受保护，停止正式容器不删除数据或镜像。

清理入口只使用标准库，默认预览；不执行全局 prune，不推断构建缓存归属。
所有实际有效的产品 home 必须通过重复 `--home` 指定，省略时只检查当前用户的标准根。
无法确认已废弃的其他安装或测试资源必须保留。

```bash
python -m research_workbench_entrypoint.docker_resources --home /absolute/product-home \
  --retired /absolute/audited-retirement.json --plan /absolute/cleanup-plan.json
python -m research_workbench_entrypoint.docker_resources --home /absolute/product-home \
  --apply /absolute/cleanup-plan.json --archive /absolute/private-archive \
  --helper-image sha256:<existing-local-image-id> --receipt /absolute/cleanup-receipt.json
```

退休清单是 `{"container:<完整ID>": "已结束任务的证据", "volume:<名称>": "废弃确认依据"}`
形式的 JSON；镜像使用 `image:sha256:<完整ID>`。仅精确核对的对象进入清单。
停止或年代久远都不是废弃证明。临时资源只有任务完成标签或显式退休证据才进入清理候选。
执行持有各 home 的生命周期/安装锁，按容器、卷、镜像顺序再次核对身份与引用。
卷备份用已有本地辅助镜像的 `sh`/`tar`，无网络、无端口；备份 SHA-256 记录后，
实际恢复到临时卷并逐文件比较，验证成功后才删除原卷。归档目录须为私有 0700，归档保持 0600。
回执逐项持久化；失败/中断停止后续处置，保留归档及剩余资源，重复执行允许已删除对象缺席。
日志仅记录稳定代码和状态，位于 `logs/docker-resources.log`。

开发及验收脚本必须在 `with ResourceSession(driver, purpose)` 中创建临时资源，
使用其 `volume()`、`run()`、`build()`，将成功、失败和正常中断收尾放在同一 finally 边界。
测试镜像为 `research-workbench:test-<用途>-<任务短ID>`，容器和卷为
`rwb-test-<用途>-<实例短ID>` 与对应 `-data`；各资源标记唯一任务身份。
异常进程退出可能留资源，须按任务证据显式清理；不得把未完成任务的 stopped 资源自动删掉。
Docker 创建/构建超时可能仍在 Engine 执行；尚未确认创建结果时，收尾明确报告未确认并记录任务身份，
不把一次查询缺席当作清理成功。须等 Engine 状态明确后按该任务身份再次核对和处置。

阶段二、三及跨平台范围已由用户明确重新开启；每个平台仍由对应宿主完成验收。当前实现边界、OS/运行模式、证据提交和未验证项见 [能力支持矩阵](research-web-platform-support.md)。安装路径存在不等于该平台能力已验收。

Python 质量整理保持公开安装参数及 coded RuntimeError 合同。内部端口 TypedDict 只描述
既有显式参数；Ruff 项目行宽与 Black/isort 同为 100，不修改依赖锁或安装行为。

macOS Docker 在全新私有 HOME 下即使 checkout 有可用 Native 环境，也可在真实 lifecycle lease 内接受 `--no-start`：产品根严格缺失、私有父目录 pin、Native PID/端点记录缺失且没有容器时，仅发布安装摘要/模式，不创建产品根、controls、PID 或端点，不分配端口。后续普通 `rwb web start` 必须重新取证并实际创建私有根；只有该调用内的真实创建证明可处理原默认端口上的其他产品监听。已有根/未知 writer 等仍失败关闭，显式端口与原认证/健康合同保持。证明不序列化；不能用旧成功清单或 no-start 调用给后续调用授权。物理首装由本平台独立验收。

创建边界沿用 Native/Supervisor 模型：mkdir 到首次 open/fstat 捕获身份并非原子；目录替换拒绝从首次捕获 inode 后成立，不承诺防御拥有可写 HOME、同 UID 且不遵守 lease 的任意捕获前替换。mode 观察使用 RuntimeModeRecord 值与既有逻辑 CAS；不声称两次合法读取之间的同内容换 inode 本身使该证明失效。

当前交付平台以 [AGENTS.md 的 Current Research Web delivery phase](../AGENTS.md#current-research-web-delivery-phase-authoritative) 为准：Mac 任务覆盖 macOS Native 与 Mac Docker Desktop；Windows/Linux 的原生适配、真机及同平台 CI 由对应设备验收，未执行项保持 NOT_RUN。Ubuntu 通用 CI 不冒充原生 macOS 验收。

Docker Doctor schema 1 的 volumes 类型为 data=bind、state=tmpfs、logs=bind、credentials=bind；logs 是新增的固定非秘密字段，verified 仍要求实际 inspect 成功，不改变安装或生命周期。

私有状态目录拒绝时，既有日志现在记录固定原因、检查阶段与变化字段名；不输出目录名、
路径或身份数值。该诊断不修复权限或重试启动，不改变依赖与一键安装流程。
源码测试不能代替新镜像的真实启动与 macOS 干净安装CI证据。
身份变化日志还区分完整root/runtime所有权对方向及parent/other_ancestor/leaf相对位置；
混合或未知变化仍拒绝，具体挂载根与认证写入层必须另行取证，不能由此自动修复。

Docker `/state` 改为私有 tmpfs（UID/GID 10001、0700、1 MiB，rw/nosuid/nodev/noexec）。
`/state/runtime` 由原严格 guard 创建；停止后丢弃，每次启动/重启由原链正常重建认证。
宿主 `run/docker/<installation-id>/logs` 独立绑定 `/state/logs`，controller 在正常生命周期
私有创建/验证该子目录，Compose 禁止自动创建宿主路径。supervisor 产品日志仍在 data-root/logs。
旧 host state/runtime 保留，不迁移认证、不自动删除旧停止容器；不符合新挂载合同的旧实例拒绝。
[Docker tmpfs](https://docs.docker.com/engine/storage/tmpfs/) 在 Docker VM 中可能进入 swap，
不能声称秘密绝不落盘。现有 CI 直接 Compose fixture 同步准备 state/logs，不扩展验收平台。

DSH 已发布运行子树内的 `doc/docs` 同名代码目录可保留（例如 yaml 的 `dist/doc`）。
Workspace 按包 files/negative 声明选择，第三方已安装 tarball 保留发布载荷，不重复套用
workspace files 声明。包顶层开发目录/文档和任意层级 Git/cache 元数据继续排除；嵌套
README 属于发布载荷元数据，不是可执行能力。真实镜像启动仍须单独验收。

Docker DSH 资产派生保留根 `node_modules` 与 `.pnpm/node_modules` 中指向已选生产包的相对别名，
供固定 DSH 从虚拟 Profile 锚点查找 optional peer。不会递归复制 `.pnpm`、引入未选开发包或新增
TypeScript 依赖；损坏或越界的生产依赖、非规范模块根、别名冲突和资产越界仍失败关闭。

Docker公开构建现在允许stdout/stderr各2MiB并流式保存脱敏进度；普通命令仍64KiB。超限或非零仍明确失败，不接受候选镜像。日志须保留在私有任务目录，不上传；本地合同通过不代表真实镜像或生命周期验收。

Docker dsh-builder 从固定 Node24.19.0 stage 同时复制 binary 和完整 headers，使用
npm_config_nodedir=/usr/local 供 fs-ext/node-gyp 本地编译，避免额外下载 headers。只在builder
设置，最终runtime无headers/nodedir ENV；不更改锁、官方APT源、TLS/签名或全局代理。
这项源码修补为一次真实重建提供新依据；先前失败日志保留，最终镜像/生命周期仍须主任务实测。

Docker CLI 可使用本机已设置的 credentials-free loopback HTTP_PROXY/HTTPS_PROXY（http或https、
localhost/回环IP、显式有效端口）；不支持SOCKS、认证URL、非回环或path/query/fragment。
大小写重复须校验后相等；两者空禁用，空/非空冲突拒绝。NO_PROXY只接受有界host/IP/CIDR/
wildcard列表并补localhost/127.0.0.1/::1；严格边界见安全清单。status/Doctor/安全stop仍可用，
不安全配置过滤并提示warning；install/build明确返回docker_proxy_configuration_invalid，纠正
本机pair/冲突后重试，不静默直连。Doctor.proxy只显示安全状态，不返回地址或列表。
仅Docker host CLI继承；Native诊断环境不放宽、不向Compose/provider/镜像写宿主127代理。
Docker Desktop Engine/build代理与CLI传输分层，真实combined构建由对应主任务验证；不改TLS、
签名、软件源、全局配置或用户Dockerconfig。镜像沿用远端已验证的 Debian 官方源 HTTPS 传输，保持原仓库与签名验证；本轮未重新构建镜像。

正常 Native auto-start 公开入口先建立/复用精确 checkout-owned `.venv`，用该 Python -I
重执行同一 setup_web.py 与原参数；sys.prefix 与已有 marker 防重复，不依赖宿主全局 Web 包。
check-only、Docker、no-start 保留 host 路径。Web 依赖就绪后，实际 manager 持原 LifecycleLock
创建 canonical 根，继续 DSH/build-lock/manifest 与正常安装门，再借同一实际 lease 启动。
证明不序列化；root/lease/原监听变化或未知新增 writer 拒绝。no-start/失败退出后不继承 fresh，
已有根重装也不认领；直接 rwb start 到不存在 custom 根仍受 build-lock 前置限制，正常
installer auto-start 是连接创建与就绪的入口。源码 fixture 不替代 main 的新 HOME 完整实测。

失败恢复先清理本次新建容器或停止本次启动的既有停止容器，再恢复端点/origin；既有容器
保留。安装摘要只在发布 inode 与字节均匹配时回滚，否则报告 recovery_unverified。

Native fresh 启动在失败后另核验本次事务的恢复基线；同一 lease/根 inode、原外来监听
身份和本次全部子进程退出均可证明时恢复原 origin/端点。否则保留事务标记与原启动错误，
附加受控恢复诊断，停止重试；该恢复基线不授予新分配权限。

Docker-only 安装缺少 Native 环境时，忙端口须核验监听归属：已证明的其他实例监听与受管
Docker 服务可继续，未知 Native 写者拒绝；无关宿主 3081 监听不阻塞 Docker 幂等启动。

可识别 Web/DSH 的其他 checkout 也可能通过环境/配置使用同一数据根；稳定 PID 或不同
源码路径不足以证明数据根不同，未知时返回 runtime_ownership_unknown。缺端点/账本的既有
根会核验旧默认8088/3081，显式新端口不能绕过。setup --no-start 或 Doctor 已创建 canonical
research-web/runtime 后，根已存在，不满足本次 start 成功 mkdir 的 fresh 证明；若日常默认
监听是数据根未知的 Web/DSH，该组合会真实拒绝，而不是自动避让成功。
macOS 现可复用 OS 当前用户标准产品根中的完整私有 Native pair，认证数据根确实不同后，
在目标真实 lifecycle lease 下保留并复查调用内目录/记录/进程观察，再允许 Docker 后续 start、
force restart 或顺序切换；不要求先安装 Native。该候选损坏、缺角色、同根、别名或任何观察变化
仍拒绝，并保留已有健康容器。Web 的根关联依赖原可信私有 launch ledger，不读取秘密或进程
环境，不宣称独立环境根证明。普通同根与无法认证的产品写者仍需所属安装的正常 stop；fresh
证明仍仅限实际首建调用，不因另一次安装或已存在根而重获权限。真实同根双模式往返仍须另验。

macOS 公开安装、start/restart 已接入私有端点记录与成对内部 origin 事务。
依赖锁保持不变，不移动、复制或轮换控制 token，也不迁移用户数据或凭据。

`--web-port <1..65535>` 可用于安装器和 `rwb web start/restart`；Native 另支持
`--runtime-port <1..65535>`，两端口必须不同。Docker 使用后者返回
`docker_runtime_port_unsupported`。显式占用返回 `endpoint_port_in_use`，不改用别的端口。
无显式参数时优先复用成功端点，再使用默认 Web 8088／Native Runtime 3081；目标运行记录
已证明静止时可分配其他回环候选。有明确 bind 失败证据、且本次对象退出/清理证明完整时，
最多执行三次启动尝试；健康/认证失败、未知归属与回滚失败不触发盲重试。
实际地址由 `web status --json`／Doctor 报告；只读诊断、logs、mode选择和 `--no-start`
均不分配端口或重绑控制 URL。Docker 容器内 8088／3081 固定，只选择宿主 Web 发布端口。
停止后出现无关宿主监听不作为停止该监听者的授权。

当前限制：已有停止 Docker 容器需要换 host Web 绑定时返回 `docker_stopped_port_conflict`，
保留原容器与接受镜像，不隐式 recreate。真实 macOS 双模式往返、镜像及干净安装 CI 未由本地
fixture 证明；Windows/Linux 本轮未验收。

## 支持范围

### Hot 配置与运行入口

Word数据投影仅使用现有Web依赖和标准报告日志；不要求旧core配置或可写镜像项目根，
不读取开发.env。无需为此新增依赖、修改容器权限或准备模型凭据。

schema21版本升级先 `./rwb hot stop`，再 `./rwb hot setup` 更新迁移和角色授权，最后启动。
周期简报使用一键安装中的产品Python与既有python-docx生成一次性报告，不新增依赖。
报告原件和回执保存在同一Hot PG，重启/模式切换从既有回执恢复；缺投影条件时保持
待处理和明确错误，不偷偷启动付费研究。旧周期无报告回执不追认新能力。

本轮增加可选 Hot 的独立 PostgreSQL/Node 组件；基础 Web 仍不要求数据库。
当前 `rwb hot` 提供非秘密配置、Native 服务生命周期、受管/外部 PG、Settings 和研究交接。
Mac Docker Desktop 复用相同逻辑数据库与代次租约；其模型能力仍受Native凭据/平台限制，
不能把采集健康作为模型可用。Hot Node 组件要求 Node 24.11+ 的 24 系列。
Native 启动后由受限 worker 持续采集明确启用的公开 feed；目录含四个官方来源和默认禁用的The File；`./rwb hot sources --json`
查询来源成功时间、错误、待解析条目和覆盖区间。采集器只跟随来源声明的同源HTTPS next链接，每轮最多三页、每页4MiB、整轮25秒。
`collection.backfillDays`为0时不翻下一页；全部已知发布时间早于范围下界时停止继续，未知时间不推造日期。
状态返回 `backfill: publisher_next_links`、范围和3页硬门；没有next仍是最新快照，有界补抓不表示完整历史。启用 Hot 不触发付费模型或研究。

干净安装仍从本页公开setup入口执行，再用 `./rwb hot configure --file services/hot/config.example.json`
保存非秘密配置、`./rwb hot setup` 初始化所选实例、`./rwb hot start` 启动、
`./rwb hot doctor --json` 检查真实状态；数据库凭据仅由受控设置/凭据后端接收。
停止不删卷，升级先停止再setup，不改旧迁移checksum。联合备份使用 `backup --include-session <UUID>`；
恢复目标必须是新库，选定快照不恢复Native执行历史。新版PG归档标记精确inventory编码；
旧未标记归档要求从保留原库重新backup，不能改manifest绕过，旧文件及卷均保留。

以下追加的阶段说明保留各阶段验收边界；例如“当时未产出报告”不是当前最终状态。
当前真实报告已验证、执行因预算结束，交付状态与执行状态分开；模型验收scope已达20次上限，
不得因刷新/安装/恢复再发付费请求。Mac干净安装与Docker实际能力以候选SHA的独立回执为准，
Linux/Windows产品验收由对应真机接手。

来源配置无需修改代码。先用 `sources --json` 取得当前 `config_revision`，然后执行：

```bash
./rwb hot source-configure fed --expected-revision 0 --disable --json
./rwb hot source-configure fed --expected-revision 1 --enable --frequency-seconds 600 --json
```

上面的 revision 仅为示例，应使用实际列表值。频率允许 60–86400 秒；0 恢复全局默认值。
修改立即写入 PG 的不可变审计并保存新版本，服务重启保留配置；暂停不会删除原文或待解析材料。
读取密钥不能执行修改。若返回 `outcome_unknown`，保留返回的 `requestId`，
用 `--request-id <同一个ID>` 和完全相同参数重试；不同参数会拒绝复用。版本冲突时先刷新来源。

事件与频道也有 Native CLI 入口（Hot 服务须已启动）：

```bash
./rwb hot channels --json
./rwb hot events --channel macro --sort importance --json
./rwb hot event <事件ID> --json
./rwb hot channel-configure gold --expected-version 0 --file services/hot/channels.example.json --json
./rwb hot event-correct --file correction.json --reason "核对原文后修正" --json
```

频道文件支持单个配置对象或示例中的 version-1 频道集合；命令选择对应频道。新增频道使用
version 0，已有频道使用实际返回的版本。纠错文件含操作 type、事件 id、expected revision，
合并/重新归属还含目标版本；完整合同见 `services/hot/README.md`。它们不接收秘密。
分页应保留第一次返回的 cutoff，再传 --offset 或 --report-offset。读取不启动模型/采集；
修改只用控制凭据并保存审计。超时/不可信或不完整回执返回 outcome_unknown、原 UUID 与
非零退出码，使用 --request-id 和原参数重放。Web Settings/页面挂载仍待实现。
Hot页面现提供 `#/workbench/hot` 和 `#/settings/hot`，后者编辑非秘密配置并显式启停已有服务。
首次依赖/数据库准备仍走上述CLI；浏览器读写不安装依赖、不接收数据库密码。Host有界惰性
桥不会在Web启动时启动Hot或查询其秘密。当前浏览器只验证未配置状态/设置可访问；真实事件
浏览、正常模型激活、完整研究、干净安装与同提交Mac CI仍须单独验证。

```bash
./rwb hot --help
./rwb hot status --json
./rwb hot doctor --json
./rwb hot configure --file services/hot/config.example.json --json
```

配置保存于产品数据根的 `hot/settings.json`；示例默认关闭、预算为零，不接收密码或 DSN。
`--data-home` 可指定隔离验证数据根，必须使用无 alias 的规范路径。状态/Doctor 不创建目录、
不触发采集或模型；未启动时不查询凭据，已启动时通过系统凭据库和签名协议查询实时状态。
数据库和模型未验证时保留 `NOT_RUN`。示例默认关闭，启用前在配置文件设置 `enabled: true`。
基础 Native 安装完成后，可在终端执行下列命令；`setup` 按锁文件安装项目内 Node 依赖，
受管模式拉取固定 PG 17 镜像、创建独立卷和受限角色，生成凭据保存于系统凭据库。

```bash
./rwb hot setup --json
./rwb hot start --json
./rwb hot status --json
./rwb hot restart --json
./rwb hot stop --json
```

`stop` 只停止经身份核对的 Hot Node 进程，不删除卷，也不停止数据库。受管数据库停止后，
`start` 会核对镜像、实例标签、数据卷和回环绑定，再恢复它。控制日志在 `logs/hot/`。
外部模式先由数据库管理员准备不同的 worker/controller/migration 角色，再在交互终端
分别执行 `./rwb hot credential worker`、`./rwb hot credential controller` 和
`./rwb hot credential migration`。默认迁移秘密引用为 `hot-migration-database`，
用 `setup --migration-user <角色>` 指定迁移账号。外部数据库只处理明确指定 schema；
Native 可执行 `./rwb hot stop --json` 后执行 `./rwb hot backup --json`，在配置的
`retention.backupDirectory` 下生成新目录。恢复命令为
`./rwb hot restore --from <备份目录> --target-database <不同的目标库> --json`。
目标 schema 必须不存在；不会删除或覆盖原库。恢复校验 SHA-256、签名及全表内容，
保持运行和来源暂停；随后通过配置文件将 `database.name` 指向返回目标库再启动。
受管模式使用镜像内 PG17 工具；外部模式需已安装 PG17 的 `pg_dump/pg_restore`，不会自动安装。
当前归档上限 256 MiB；超限明确失败，研究快照尚未纳入。`archive-attempt.json` 保存归档状态，
未知结果禁止重复执行，自动核验/解除路径待实现。完整安装 CI 仍待完成。
当前进程与 PG 验证使用隔离凭据 backend；
系统 Keychain 持久化尚未实测，详见任务报告。

内部服务使用仅绑定 `127.0.0.1` 的签名协议，校验实例、模式、代次和操作权限，消息不携带
原始控制 key，响应也验证签名。它不暴露 SQL、路径或凭据管理给浏览器或模型。

当前是本地 Web 产品，支持 Native 与 Docker 两条安装路径；不安装 Tauri、桌面 sidecar、数据库或桌面安装包。两种模式使用同一源码、`runtimes/research_web.json`、Web 依赖锁、固定 DSH 与顺序共享的产品数据目录。前置条件按模式区分：

- Docker 新实例入口：shell、Docker Desktop、可用 Engine/buildx，以及访问镜像和固定 DSH 依赖的网络；无需宿主 Python/Node。legacy Python Docker CLI 仍需宿主解释器。镜像使用固定 Python 3.12、Node 24 和非 root 用户。Windows cmd 保留 legacy 路径；凭据 ACL 未证明时以 `docker_credentials_acl_unverified` 失败关闭，不称为 Windows Docker 已验收。
- Native：Python 3.12、Node.js 22.19+（22 系列）或 24.x、Git；Node 23 和 25+ 不受支持。
- Windows Native：Visual Studio 2022 Build Tools 的 “Desktop development with C++” 工作负载；固定 DSH 的
  `fs-ext` 原生模块需要本机编译，安装器不会静默安装或修改系统工具链

Wind、iFinD、Office 等厂商/系统软件是可选能力，缺失不阻止 Web 主体启动。模型密钥、`CJ_KEY`、
Cookie 和账号只在本机设置页录入，不进入代码包、安装清单或日志。

## 开发与验收责任

24GB Mac mini 负责主开发、Docker 构建/测试、常驻服务、macOS 本地验收及适用 GitHub macOS CI；MacBook Pro 负责远程编辑与操作。Windows/Linux 真机负责既有功能的本平台原生适配、本地及远端同平台 CI 验收；发现通用功能缺陷时交回 Mac 开发任务。

各宿主任务只以本平台验收为完成条件；其他平台保留待验收与交接记录，不阻塞本平台任务，也不因 Mac 验收通过就宣称跨平台支持。Linux 适配职责不表示当前安装器或桌面包已经支持 Linux；支持声明仍须有实际证据。详细任务与总体验收的区分见 [Agent 任务路由指南](AGENT_WORKFLOW.md)。

## 公开入口

受管启动使用产品Node preload将启动认证信息交接到既有私有auth控制文件，普通runtime.log不保存认证链接；正常管理器完成Cookie交换，不从旧日志恢复认证。安装依赖、固定DSH版本和构建闭包不变，独立实例仍须有真实受管环境及匹配安装/build-lock证据；测试根准备不等于干净安装CI通过。

安装完成后，在设置的模型服务页录入固定 Runtime 支持的 DeepSeek 配置。留空保留、填写替换、独立清除；保存只设定新会话模型，已有会话保留选模，任务运行时拒绝变更。模型页分别显示保存、Runtime 应用、凭据与最近真实生成；生成测试显式调用模型并消耗少量额度，前置检查最多 30 秒、生成执行段最多 60 秒、取消等待最多 3 秒，不由安装或 Doctor 自动执行。

macOS Native 模型凭据使用已有 Web 依赖 `keyring==25.7.0` 的 macOS Keychain 后端；owned overlay 使用产品受管 Python 的私有 stdio 桥接，固定 DSH 版本和构建闭包不变。命名空间由规范化 data home 派生，重启从同一系统账户恢复；不读取开发者 Codex/Claude 配置，不导入环境、旧 YAML 或任何 `.env`。旧模型 Key 不自动迁移，需在本实例设置页重新录入。Host 认证 record 独立存于 Runtime home 的 `.browser-credentials.yaml`，保留固定 DSH 锁和更新语义，不持有模型 Key。Keychain 拒绝/不可用及非 macOS 后端均明确失败，不采用文件回退。产品锁、安装器与 workflow 未变，仍须当前代码的 macOS 干净安装 CI 证明兼容。

Docker 模型凭据由 owned overlay 显式选择 `docker-encrypted-file`，并绑定
`/run/rwb-secrets/private`；私有 stdio 桥接不继承 API Key 环境变量。后端复用原有
no-follow、0700/0600、固定 inode 锁和有界文件读写，在 `models/` 子目录保存 Fernet 密文
和一次创建的主密钥；复用已有锁定的 `cryptography==50.0.1`，不升级包版本。两个模型 ref
独立，密文绑定 data-home 命名空间及 ref；缺失/损坏主密钥、损坏密文或不安全目录均失败
关闭，不自动轮换、导入或清空旧凭据。主密钥与密文同卷，管理员及同 UID 仍属于信任边界。
Doctor 只声明实现，Runtime API 的存储投影为 `docker_encrypted_file`。现有数据、通用业务
凭据和 Host 认证保持；模型保存不发起推理，生成测试须用户显式请求。

macOS：

macOS Docker 入口（本任务已执行隔离安装与生命周期验收，证据见支持矩阵）：

```bash
./setup-web.sh --runtime docker
./rwb web doctor
```

当前 macOS Native 入口；无参数 `./setup-web.sh` 也默认 Native：

```bash
./setup-web.sh --runtime native
```

Windows Docker 对应入口（当前 ACL 门仍可能失败关闭）：

```bat
setup-web.cmd --runtime docker
rwb.cmd web doctor
```

Windows Native 替代入口：

```bat
setup-web.cmd --runtime native
```

跨平台底层入口：

```bash
python scripts/setup_web.py --runtime native
```

`--runtime` 缺省为 `native`，包括 shell、`.cmd` 和底层 Python 入口；不会因 Docker 已安装而改变旧调用语义。Docker 安装路径会做只读 preflight、构建受管镜像并核验镜像身份；只有已验证的项目安装身份且当前运行时/端口无冲突时才发布安装摘要和选择 Docker。`--no-start` 仅跳过启动，不代表镜像已实际健康运行。Docker 安装摘要为 `~/.research-workbench/install/docker-manifest.json`，与 Native 安装清单分开。

Docker 构建使用每次独立的候选 tag；接受摘要记录不可变 image ID，后续 start/Doctor 不依赖
`research-workbench:local` 当前指向。摘要通过私有文件、长度、无 alias 和字段校验，再核对
Web 锁、Compose、Python/Node 与 CJPY/DSH 构建合同；缺失、损坏或合同不一致会失败关闭。
默认启动有界等待容器健康检查证明 DSH/Web 同时 ready；starting 超时、unhealthy 或退出都
不会发布成功模式或打开浏览器。失败只删除本次新建且重新确认归属的容器，保留既有容器、
数据和凭据。显式 `--no-start` 仍允许仅接受已验证构建，不宣称实际 ready。
候选启动或发布失败保留先前接受的镜像；模式提交失败时恢复先前摘要。已有容器使用其他
image ID 时，普通安装返回 `docker_upgrade_requires_container_disposition`。显式 `--repair`
可在确认旧受管容器停止、端口空闲后再次检查归属，并用非 force 的精确 ID 删除该停止容器；
并发启动时删除失败关闭。旧接受摘要和旧不可变镜像、产品数据、凭据始终保留到候选接受，
失败时可按旧接受合同重新 start。若同时修改了锁或 Compose，需要恢复旧合同后才能按旧镜像
启动；不会用不匹配的新合同启动旧镜像。`--no-start` 同样要求显式 repair 才处置旧容器。
相关错误为 `docker_manifest_missing`、`docker_manifest_invalid`、`docker_build_contract_mismatch`、
`docker_image_mismatch`、`docker_ready_timeout`、`docker_services_unhealthy`、`docker_rollback_failed`。

Compose `up` 自身非零或超时后也执行一次有界恢复核对。新建调用使用临时配置写入一次性
launch label，只有启动前不存在、label/安装归属/候选image全部匹配的精确容器才清理；
并发或无法确认的实例保留，原启动issue后追加 `docker_rollback_unverified`。清理执行失败
追加 `docker_rollback_failed`，不覆盖原up错误或自动重试删除。`--no-recreate` 保留既有停止容器。

下述 `.venv` 和宿主 Node 说明仅适用于 Native。Native 默认流程会检查前置条件、创建项目自有 `.venv`、按哈希锁安装 Web 依赖、校验并安装随包
`cjpy==0.5.2`、构建固定 DSH、启动 3081/8088 并打开浏览器。可用参数：

- `--check-only`：只检查，不写入。
- `--repair`：Native 只修复带本项目所有权标记的 `.venv` 或 DSH 目录；复用 `.venv` 前以 15 秒上限
  验证其中的 pip 可响应，失败时把旧环境保留为 `.venv.failed-<id>` 后原子创建新环境；未知目录
  仍拒绝覆盖。
- `--no-start`：安装完成但不启动服务。

Docker `--repair` 重复有界构建和镜像身份验证，不删除产品数据、未知容器或 Native 环境。Docker 安装可能因远端镜像、APT、npm/pnpm 或 GitHub 网络失败；不得把 `--check-only` 成功或本机源码测试当作完整构建成功。

Docker DSH builder 的固定 `pnpm@11.7.0 install --frozen-lockfile` 命令局部设置
`--network-concurrency=8 --fetch-timeout=120000`，将下载并发限制为 8、单请求期限设为
120 秒，默认重试仍为 2 次。这不是整个构建步骤的总期限；Native、最终 runtime 环境、
registry、TLS、签名和最低发布时间策略保持不变。参数调整不证明网络故障根因或锁定
tarball 下载已经修复，仍须以公开安装入口的真实新镜像构建和健康检查验收。

容器启动时，Web 每轮完整页面就绪探测共用最多 3 秒（Runtime API、首页与主静态模块），
并裁剪到剩余启动期限；DSH 每轮仍为 0.25 秒，各角色启动期限仍为 35 秒。
这只修正完整页面探测的预算，真实镜像安装与生命周期验收须另行取得证据。

## 模式、生命周期和目录归属

安装后先查看当前模式；仅需切换时使用 `runtime use`，不要把两个方向当成连续安装步骤：

```bash
./rwb runtime status --json
```

```bash
./rwb runtime use docker --stop-current
```

```bash
./rwb runtime use native --stop-current
```

选定 Docker 后，可分别运行这些生命周期与诊断命令：

```bash
./rwb web start --no-open
./rwb web status --json
./rwb web doctor --json
./rwb web logs --tail 100
```

Docker 在运行中无法认证证明研究空闲；重启必须显式 `--force`，会中断研究：

Docker 停止后只等待已验证的宿主 Web 映射释放，macOS 默认最多 120 秒；内部 DSH 3081
不属于宿主映射，不等待或停止其他根 Native 监听。持续占用仍返回 `runtime_ports_not_released`。

```bash
./rwb web restart --force --no-open
```

停止当前受管服务：

```bash
./rwb web stop
```

Windows 将入口写为 `rwb.cmd runtime status --json`、`rwb.cmd runtime use docker --stop-current`、`rwb.cmd web doctor --json` 等对应命令；这些是接口说明，不表示本轮已在真实 Windows 上跑通 Docker。`runtime use` 默认不停止当前服务；存在运行中的旧模式时必须显式提供 `--stop-current`，且仅在旧进程/容器归属可验证时停止。未知端口占用、无法确认的 PID/容器、活动研究或状态异常均失败关闭；不要手动改模式记录来绕过。运行时选择保存在私有 `install/runtime.json`，无需 `.venv` 即可路由 Docker 命令；Native 命令仍进入 Native 环境。

已确认运行中的 Native 实例在 `--stop-current` 的公开停止成功后，模式切换最多等待
45秒让停止前的两个 Native 端口释放；超时仍为 `runtime_stop_failed`，模式保持原值。
该等待不停止占用者，不等待外来默认端口或 Docker 内部端口；随后仍须通过原归属、
两模式状态、锁与模式 CAS 复查。未授权、未知归属、已停止或停止失败不进入等待。

`runtime use` 最终停止复查仍严格返回 `runtime_stop_failed`。stderr 的
`runtime_switch phase=finalize` 诊断仅包含固定模式、`report_not_ok` / `still_running`
以及受控 issue；未知代码映射为 `unknown`，仍运行时为 `none`，不输出原 report、路径或秘密。
这只补足失败归因，不证明历史切换失败已修复；锁、归属、顺序停止和模式 CAS 保持原合同。
Native status 原拒绝点另记录固定 `status_precheck` / `status_child` / `status_postcheck`
阶段；子进程拒绝只记 `report_not_ok`，不回显其 issue 或 stderr，也不新增探测或重试。

两种模式依次使用 `~/.research-workbench/research-web/` 中的同一会话、资料、附件和产物，绝不能同时写入。Native 的 PID、认证和运行状态位于 `~/.research-workbench/run/`；Docker 的临时状态位于容器 `/state/runtime`，持久日志位于宿主 `run/docker/<installation-id>/logs`，容器归属由项目、服务、安装身份、镜像、挂载及端口核对，不复用 Native 的状态/认证文件。Docker 凭据存于 `secrets/docker/<installation-id>/` 并单独 bind mount 到容器；Native 仍使用宿主系统凭据库，模式切换不复制或迁移密码/令牌。Compose 只将宿主 `127.0.0.1:8088` 发布给浏览器；DSH 3081 仍留在单容器内部回环。容器以非 root、只读根文件系统、受限能力和显式可写挂载运行。

Docker 的挂载根与实际私有目录不同：`/state` 是私有 tmpfs，DSH 状态和认证实际位于
`/state/runtime`；`/run/rwb-secrets` 仍是凭据 bind 根，File backend 显式使用
`RESEARCH_CREDENTIAL_HOME=/run/rwb-secrets/private`。supervisor 以容器 UID 10001 在首次
认证、健康探测和子进程启动前创建 0700 私有叶，重启时重建状态、验证并复用凭据。Docker Desktop 可能把
宿主创建的 bind 根呈现为 UID 0；不会因此放宽私有叶 owner/权限/no-follow 检查，也不会
chmod/chown 挂载根。`LOG_DIR=/state/logs` 单独绑定原宿主日志子目录，避免导入期日志创建
影响状态叶。用户 data-root 与 Native 路径不变，Inspector 严格执行新的完整挂载合同。

首次 mkdir 还可能使固定 bind 根的可见 UID/GID 从 0:0 变为容器用户。Docker-only 准备器
仅对缺失的 `/run/rwb-secrets/private`、`/data/research-web/logs` 分阶段：
保留 no-follow 父目录FD安全创建0700叶，固定父节点的dev/inode/mode和路径/FD一致性必须
保持，创建阶段仅允许可信root→当前UID/GID映射；随后重新进入原完整严格校验，确认新叶
仍为本次创建对象，才访问认证/凭据或启动进程。已有叶及自定义路径无此创建例外。

Docker 容器无法等同宿主系统集成环境：Office/Wind、宿主凭据库、Tabbit 等需要 GUI、驱动、会话或本机 CLI 的能力不得仅因目录可见就标记为可调用。模型密钥须在选定模式中重新配置；Doctor/日志输出不应包含秘密或用户文件正文。`./rwb web logs --tail 100` 为有界尾部；Docker 的 `--follow` 最多读取 300 秒，每条输出流上限 64 KiB，超时或超限会结束读取，退出读取不停止服务。Doctor 的稳定 `issues` 可用于定位：`docker_cli_missing`、`docker_daemon_unavailable`、`docker_compose_missing`、`docker_architecture_unsupported`、`docker_port_8088_occupied`、`docker_port_3081_conflict`、`docker_ownership_mismatch`、`docker_build_not_ready`、`docker_data_home_unsafe`、`docker_credentials_acl_unverified`、`docker_services_unhealthy`、`runtime_stop_current_required`。按代码修复前置环境或停止已确认归属的旧模式，再重试；不要删除未知容器或修改状态文件。

升级时先 `web stop`，更新受审源码和锁后用对应 `--runtime` 重建/安装，执行 Doctor、status 和实际启动验证；不能把旧安装摘要视为新代码证明。修复用同一模式的 `--repair`，先保留现有数据并核对所有权。卸载运行部分可停止服务、移除自己受管的镜像/容器或 Native `.venv`；产品数据、Docker 私有凭据和 Native 系统凭据默认保留，需先另行备份并取得明确授权才清理。没有自动执行跨模式凭据迁移或破坏性卸载。

安装器只会在当前 `.venv` 能从 checkout 加载 `app.research_web.main:app` 后写入 `installed` 清单；
该 Web import readiness 最多等待 300 秒，用于完成云盘/FileProvider 冷文件的首次读取。超时或导入
失败返回 `python_web_import_failed`，不会把仅依赖已安装但当前 Web 入口不可加载的环境标记为完成。
开始修改安装器自有环境前，旧成功清单会被原子替换为 `installing`；任一步失败都保留该非完成
状态，Doctor 与 start 因而不能继续信任上一次安装的陈旧 `installed` 证据。

Node 选择顺序为：调用方显式传入、`RESEARCH_NODE_BINARY`、可执行的 Codex bundled Node、PATH。
安装器会把选中 Node 的目录放在 npm/Corepack/DSH 构建子进程 PATH 首位，避免版本检查使用 Node 24
而原生模块实际由 PATH 中的 Node 25 构建。Node 23 与 25+ 仍关闭失败，不会自动下载替代运行时。

安装完成后可运行：

```bash
./rwb web doctor
./rwb web doctor --json
./rwb web start --no-open
./rwb web status
./rwb web stop
```

Windows 将 `./rwb` 换成 `rwb.cmd`。Doctor 的 JSON 只包含版本、摘要、端口和健康状态，不输出路径、
环境变量值、凭据或用户文件正文。
若 checkout `.venv` 缺失、所有权标记不完整或解释器不可用，顶层 `--help`、`web status` 与
`web doctor --json` 仍由仅使用系统 Python 标准库的受限入口提供帮助或安全诊断；该入口拒绝
`start/restart/stop`，不读取 Runtime Cookie，也不改写 PID/state。系统 Python 也缺失时，入口返回
`python_runtime_unavailable` 并提示重新运行公开安装器。
该限制只适用于选中的 Native 模式：stdlib bootstrap 先选择部署模式，Docker 命令在 Native
环境缺失或损坏时仍可路由。Native 的 `web status --json` 同样提供 schema 2 的安全事实；
工作树复用公共 checkout 的 `.venv` 时按该环境所属根验证安装标记，不回退导入全局产品包。
Doctor schema 2 区分 `installation_ok`、`product_ready` 与 `model_ready`。服务状态按 state、真实 PID、
启动身份与命令归属、监听 PID、DSH 协议、Web HTTP 逐级核对；PID 文件或开放端口单独存在都不构成
ready。Node 22.19+（22 系列）或 24.x 由安装器与 Doctor 使用同一版本合同核对，其他版本或畸形
输出报告独立 issue。模型配置、凭据或目录问题只列入 warning，不阻止 Web 与设置页启动；Doctor 不
通过真实生成请求测试模型密钥。
`start` 在已确认死亡且端口关闭时恢复 stale state；归属明确但不健康的 DSH 只有在只读核对确认
没有活动研究后，才按 Web → DSH 的停止顺序重建。活动研究存在或无法核对时拒绝自动停止，并提示
显式 `rwb web restart --force`。随后依次等待 DSH、Web Runtime API、首页与 `/static/app.mjs`，
并复查最终产品就绪状态；未就绪时返回非零退出码和具体健康 issue，不会误报启动成功或打开浏览器。
归属不明的 PID、监听者或
损坏且仍可能活动的 state 会失败关闭，不接管或终止未知进程。生命周期操作由同一排他锁串行化；
浏览器打开失败会返回 `browser_open_failed` warning 和可复制 URL，已健康服务继续运行。
`rwb web start` 会在创建 3081/8088 子进程前复用 Doctor 的安装检查。若 checkout `.venv` 不受安装器
所有、锁摘要不符、CJPY/Node/DSH 未就绪，命令立即列出稳定 issue code，并提示重新运行上述安装器；
它不会先创建候选 Runtime 再等待健康超时。
安装成功还会从已验证 DSH state 原子刷新 `research-web/runtime/build-lock.json`；Doctor 返回
`dsh.runtime_lock_matches`，锁缺失或与当前 commit/closure/文件数不符时报告
`dsh_runtime_lock_mismatch`，不会把“安装清单有效”误报成 Runtime 可启动。
锁路径逐级拒绝符号链接和 Windows reparse point；POSIX 使用 no-follow 目录描述符完成 0600 原子
替换并拒绝 hardlink，Doctor 以相同边界有界读取。写锁前会把当前用户拥有的产品 data home 收紧为
0700；未知 owner 或 alias 不自动修复。closure 文件数只接受 JSON 整数，不接受浮点等价值。

## 依赖与固定制品

- `.venv` 位于 checkout 根目录，只由安装器管理，不写入全局 Python。
- `requirements/web.in` 是 Web 直接依赖；`requirements/web.lock` 是 Python 3.12、macOS/Windows 通用、
  带哈希的解析结果。用户端只消费锁文件。
- 根项目包以 `--no-deps` 安装，避免把历史 PostgreSQL、LangGraph、量化和桌面依赖引入 Web 环境。
- `vendor/cjpy/0.5.2/` 保存批准的 Apache-2.0 wheel、来源、许可证与闭合哈希清单；禁止回退到
  PyPI 的旧版 CJPY。`vendor/dsh-tabbit/0.3.4/` 的归档、MIT License 与 manifest 同样属于固定供应
  闭包。仓库属性禁止 Git 在 Windows checkout 改写这两个制品目录的字节，确保同一清单摘要可在
  macOS 与 Windows 验证。
- DSH 只从 `Leon-Huang001208/deepseek-harness` 获取提交
  `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`，使用 `pnpm@11.7.0` 和 frozen lockfile 构建。
  Git clone、固定提交 checkout 与后续干净工作树校验都使用同一组命令级配置：
  `core.longpaths=true`、`core.autocrlf=false` 和 `core.eol=lf`，因此 Windows 不依赖机器级 Git
  长路径或换行配置。固定提交包含 Git symlink；Windows 额外统一使用 `core.symlinks=false`，接受 Git
  官方的普通文件表示但仍拒绝其他修改。首次启动会先用固定 DSH 模板
  初始化 `web` Profile，再写入已校验的 Tabbit bundle；
  不能依赖开发机残留的 `profiles/web/package.json`。
  Windows Node 构建只额外继承 PowerShell 模块、Program Files、ProgramData、系统盘与 Common
  Program Files 的标准发现路径，使 `node-gyp`/MSBuild 能定位并运行用户已经安装的 Visual Studio
  工具链；密钥和其他应用环境变量仍不进入子进程。
  安装器固定闭包文件数，首次成功构建后将当前安装目录对应的闭包摘要写入受管标记和安装清单，
  后续 Doctor 按该本机证明检测篡改。CSS Modules 会把绝对构建目录影响到产物摘要，因此不把任意用户目录误声明为
  同一全局摘要。GitHub 不可达、提交/来源/文件数不符，或本机证明后续不匹配时，安装关闭失败，不使用任意本机 DSH。
  DSH 构建子进程使用用户私有数据目录中的 Corepack shim；嵌套构建也固定解析 `pnpm@11.7.0`，不依赖全局 pnpm。

安装清单写入用户私有 `~/.research-workbench/install/manifest.json`，仅记录代码提交、Python/Node
版本、Web 锁摘要、CJPY 版本/摘要、DSH 提交/闭包和诊断状态。安装日志位于仓库 `logs/setup-web.log`。
安装子进程只透传平台基础变量和标准 `HTTP(S)_PROXY` / `ALL_PROXY` / `NO_PROXY` 网络配置；Git 可使用宿主的
SOCKS 代理，pip 与 Corepack/Node 仅保留其支持的 HTTP/HTTPS 代理。大小写代理变量采用同一协议过滤，
被过滤时日志只记录变量数量，不记录代理值，也不修改宿主环境。macOS 构建原生 Node
模块时，安装器通过 `xcrun` 发现当前 SDK 的 libc++ 头文件，不写系统路径。`CJ_KEY`、模型密钥及其他应用秘密不会传给安装命令。

## 天软状态

安装成功只证明 `cjpy==0.5.2`、`requests` 与 `urllib3` 可导入。没有 `CJ_KEY` 时，天软必须显示
“依赖已安装但待配置”，`configured=false`、`callable=false`；保存后的 Key 在每次探测和查询时从
系统凭据库动态读取，不要求重启。认证、权限、限流和厂商不可达分别显示，不能把依赖安装成功当作
真实数据成功。

## 后续迭代门禁

任何 Web 功能、Python/Node 依赖、DSH、CJPY、启动或配置流程变更，都必须重新核对本文件、
`requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py` 和 Doctor。仓库级
`.github/workflows/research-web-bootstrap.yml` 对相关 PR 与主分支更新在干净的 GitHub `macos-14`
runner 上运行公开安装入口、构建固定 DSH、启动 3081/8088、检查 Doctor，并验证无凭据天软不会
误报可调用。本机 macOS 验证必须先通过，但不能替代该远端干净环境门。Windows Web workflow 仅
保留手动入口：当 policy 选择 Windows gate 时，必须在 Windows 真机 checkout 待验 ref，从该机以
`git rev-parse HEAD` 的 exact SHA 发起 GitHub `windows-2022`；Mac 不发起该 workflow。GitHub Windows
结果与 Windows 真机安装、升级、用户目录、Office/Excel/Wind 结果分别记录，任一未运行均不得标记为
通过。该边界不改变桌面/Tauri/sidecar 的独立 Windows 门禁。
Linux 真机任务负责 Linux 适配、本地验收与对应 GitHub CI；其他平台门交接对应真机，
不阻塞 Mac 本平台任务，跨平台发布仍需各目标平台的真实证据。
Bootstrap 的 macOS 验收还要求 Doctor schema 2 的安装/产品 ready、双服务 ready，以及首页和主
静态模块实际可读取；本机运行和单元测试不能替代该干净 runner 的结果。

维护者更新直接依赖后，用 Python 3.12 重新生成锁：

```bash
uv pip compile requirements/web.in \
  --universal \
  --python-version 3.12 \
  --generate-hashes \
  --no-strip-markers \
  --output-file requirements/web.lock
```

提交前必须从干净 checkout 运行一键安装；不能以开发机已有 `.venv` 或全局模块作为交付证据。

固定DSH为0.2.1-alpha.1兼容候选，闭包16097项。构建需要所选Node发行版附带include/node开发头文件；缺失时保留构建错误，不能复用旧安装成功标记。

## 设置闭环阶段3：当前能力范围

能力准入和脚本精确读取范围使用受管产品Python/Node及现有私有数据通道，不新增依赖或修改固定DSH。升级时保留旧会话材料，旧资源全集不是新执行许可；部署仍需本平台干净安装CI，不由本机已安装环境替代。


## 单一兼容模型连接

模型服务页现提供多个命名连接；每个连接仍遵守以下同一兼容协议合同。旧配置与两个原凭据账号原位保留，第一次显式修改才增添非秘密 profile 索引；不自动搬迁 Key、会话或日程。DSH 两个逻辑 ref 由产品凭据层映射到各连接的独立物理账号。公开安装入口、依赖锁与固定 DSH 不变。见[模型服务商与连接](research-web-ui.md#模型服务商与连接)。

新受管 Docker 实例的模型后端可由管理员显式初始化为实例隔离的 AES-256-GCM 存储，
复用锁文件中 cryptography 50.0.1，并将其列为 Web 直接依赖；版本与哈希未升级。
Native macOS 的 Keychain 选择及安装流程保留。Docker 操作、主密钥只读挂载及最小恢复材料
见 [Docker 手册](research-web-docker.md)，不能把安装成功作为模型生成验收。

一键安装包含产品兼容文本/流式适配，固定DSH、Python/Node依赖锁不变，不安装本地模型服务或下载权重。用户另行配置自己实际可用的HTTPS兼容服务或本机loopback端点；localhost指Native后端设备。无Key不是旧文件/环境回退，Doctor/服务健康不发起隐式模型请求，真实模型与工具验收仍需独立证据。

Docker 两个 APT 安装阶段使用 Debian HTTPS 源，保留 archive keyring 签名校验、原有包与锁定基础镜像；网络代理仅按宿主/构建环境配置，不禁用证书或包认证。HTTPS 源切换不证明 Linux/Windows 真机或 CI 已通过。

Docker DSH staging 按包发布载荷收录运行时代码：开发目录名称只在包根解释，嵌套 dist/doc 等代码目录不能当文档删除；.git 等元数据与 node_modules 独立包图仍受安全过滤。镜像健康还须真实证明 DSH/Web，不能只看构建与 manifest 哈希。

Docker Desktop 的共享文件系统可能反复刷新 bind 根的 UID/GID 视图。容器 `/state` 使用 Linux 私有 tmpfs，避免将临时认证状态置于该祖先；数据与凭据继续使用独立持久 bind。原 dev/inode/mode/uid/gid、no-follow 与私有叶检查保持，临时状态丢失不删除研究数据或凭据。`/state/logs` 为临时内部日志，容器 stdout/stderr 仍由有界 Docker logging driver 保存。

Docker Engine 可只在 `HostConfig.Tmpfs` 中表示 tmpfs，不将它们列入 `Mounts`；控制器兼容列表完全省略或完整三项表示，仍强制 HostConfig 的固定路径、UID/GID、权限和安全选项。部分、重复、别名或额外挂载均拒绝。

macOS Docker 停止后回环端口的非监听绑定保留可能延迟释放；默认最多等待120秒，其余宿主默认10秒，显式等待参数保持。仍必须实际释放IPv4/IPv6绑定，超时失败关闭；不使用SO_REUSEADDR或只做连接探测来绕过占用。具体内核延迟原因未独立证实。

Hot 模型默认关闭；现有 Native 启动桥可按 model.enabled/scopeId 装配固定 DSH 文本能力，只有指定 schema 的既有预算授权、每日限额、当日定价和受控凭据都就绪才激活。配置并不授予付费额度。缺条件时模型 blocked_model，公开来源和读取继续可用。创建新授权范围及当日定价刷新的一键流程、授权 worker 的干净安装验收仍待补齐；现有 Web Node22 CI 不能替代 Hot Node24 安装验证。

应用升级到包含迁移14的版本后，先停止 Hot 并运行 rwb hot setup，再用 model-authorize 明确付费授权；配置本身不创建额度。model-attempts 可用普通角色读取额度/尝试，model-terminate 保留未知预留，未确认的操作阻止启动。受管冷库仅由明确管理操作验证后恢复；只读查询不启动数据库。定价刷新入口和授权 worker 干净安装仍待验收。

当日费率可通过 model-pricing-import --file pricing.json --verify-official-pricing --reason "已核对官方峰值费率" 配置，无须改源码；停止Hot、用户核对官方页面后导入并重启。默认不自动下载或确认价格；同值重放补验耐久性，非零 durability unavailable 不代表当前文件未可见。

实际两事件浏览器验收通过已有开发环境和隔离凭据/离线研究客户端，不能代替干净安装或系统凭据完整链路；所有安装/正式模型/研究门仍以支持矩阵和任务证据为准。

Hot简报冻结核心不引入新依赖或schema迁移；只读取得截止时点版本并内部导出Markdown。当前没有公开简报命令或DOCX安装能力，干净安装及定时/研究链路仍按原验收计划保持待验证。

Hot迁移15增加持久简报版本与请求审计；升级时先停止Hot并执行既有setup，再启动。版本数据随Hot数据库归档，既有预算不重置；当前公共简报命令、网页生成、DOCX和研究快照联合恢复仍未提供。

迁移15之后可从Web事件详情生成简报，在简报页预览并下载固定版本Markdown。沿既有Web依赖与HotNode，不新增包；RWB_HOT_TEST_PYTHON仅测试夹具选用已安装Web解释器，不是产品配置。当前干净Mac安装、DOCX、真实模型worker及研究联合恢复仍按原计划待验收。

原验收库已由停机fixture迁移至15，实际浏览器完成AI/宏观简报与固定版本Markdown。该夹具保留原实例/预算账本，modeldisabled且研究offline；角色收尾独立于恢复审计。此证据不替代干净安装、正常Keychain生命周期、DOCX或正式研究。

## 可选 Office 自动验证

### 华安ETF周报的可选API生产合同

公开安装入口仍安装同一Research Web，不自动安装WindPy、登录厂商、迁移报告或启用日程。
主管理员在既有Workflow详情准备并发布`huaan-etf-weekly-v1`后，仍须完成SDK权限、同源Excel对照、
跨市场交易日历／收盘定义和经济日历数据集验证。SDK及厂商许可是可选外部前提，安装和凭据配置须
另行授权；不得从非官方同名包自动获取SDK。秘密不进入版本包、锁文件、日志或CI产物。

`rwb web doctor --json`的`weekly_report`只做零厂商调用的依赖摘要：`dependency_ready`、`status`、
`code`、`source_contract=not_checked`，以及`live_acceptance`／`model_acceptance=NOT_RUN`。
可选SDK缺失不改变主体安装ready语义；Doctor不登录、刷新Office、查询厂商或发模型。
Doctor的主体安装就绪、Office诊断和既有Wind通用状态不能认证该私有API链的真实取数。
Workflow详情分别展示依赖、待配置／未核验和最近运行；未取得源覆盖及质量证据时保持阻断。
缺少可选SDK不应伪报可调用，也不应把基础研究安装误判为厂商已登录。保留三份底稿和原母版，
只在Run副本上投影本期数据；原生Office刷新与API逐组迁移的边界见[周报生产合同](research-web-etf-weekly-production.md)。

本能力不扩展Docker宿主Office桥或其他平台支持；本机验证、同候选macOS干净安装CI、真实取数／
成稿与三个周周期分别取证。常驻部署另行授权，源码安装成功不启用正式周报日程。

安装/启动成功不代表 Office 可调用。默认不开启真实验证；在设置 → 本机集成一次开启所属实例的Word、Excel、PowerPoint自动验证，或逐项开启/关闭。会创建、保存、重开并清理登记的测试文稿，保留验证记录（沙箱文件经归档后精确删除，合成副本由私有run目录按原容量/期限保留），可能出现系统提示；提示只能人工处理。有效24小时证据复用，失败不自动重试，关闭后不再启动，冷启动不重放旧任务。Wind最多5分钟，厂商调用不在此开关内。

`rwb web doctor --json`的office_auto_verification仅显示所属实例开关/未知状态、应用范围、人工提示与关闭位置，不发起真实操作，不影响主体安装就绪。未知、未发现、失效及不适用不会提升为可调用或一概归为系统故障。本轮不改安装依赖或一键启动逻辑。

2026-10-09追加授权收口：Office成功且关闭确认后，仅归档登记的合成文稿到既有私有验证run目录，再清理沙箱副本；成功marker移除，仍沿原16项/512MiB/24小时有界保留策略回收，不新增执行器或任意路径接口。Office开启改用页内说明、确认/取消按钮，系统权限弹窗仍由人工处理。


Hot原件冻结新增同包读取方法，不增加产品依赖或数据库迁移（仍schema15）。Node仍要求24系列，原Web干净安装/Hot Node装配问题未因此解决；必须按Hot安装入口和同候选Mac CI继续验收。冻结原件与DOCX内核成功不证明干净安装、实际凭据或Docker产品可用。


包含schema16的Hot版本需在停止Hot后通过同一rwb hot setup迁移并重新核对角色授予；不得修改旧迁移checksum或删除数据卷。新迁移追加研究固定输入、映射与审计，不迁移其他RWB业务。当前快照/故障注入成功不替代干净安装及同候选Mac CI，付费DSH执行仍未由本轮认证。

schema17的研究模型私有RPC桥不新增依赖或迁移；它继续要求既有Hot Node24、当前Native价目
及原预算授权。只有完整流回执/缓存返回允许2MiB签名帧，普通请求保留原上限。DSH流消费者
尚未装配，因此该桥的本机PG回归不替代干净安装、Mac CI或正式研究产物验收。


2026-10-13续跑：停机执行 `rwb hot setup` 追加migration18后，可用 `model-amend-tokens` 明确提高已有scope的累计/单日token限额。原计费历史及次数/费用上限保持；另把本实例budget.maxTokensPerDay设为批准值。无新增依赖。原验收库现schema18；研究已真实调用但未生成报告，干净安装CI仍待执行。

Hot冻结FinGPT的research-hot-frozen声明随现有runtime YAML包数据安装，无新依赖；
仍需候选Mac Bootstrap干净安装验证。普通研究/Claw不换preset，已存在Hot会话保持其原组合。


Hot报告列表/显式核对/Word下载复用现有app与python-docx，无新依赖。模型预算不变；源码本地回归和隔离浏览器不替代候选Mac干净安装CI。

AES 载入进一步认证全部既有模型记录；错误密文树/实例绑定明确拒绝，安装依赖和正确旧记录格式不变，不自动转换或生成替代主密钥。

## 框架嵌入资产安装 · 2026-10-14

十一套看板资产随 Git checkout 提供，公开安装器继续使用锁定依赖与固定 DSH，无额外 Node/Python 依赖和开发服务器。Gold／Dollar 核心使用本站原生快照；其余九套是明确标记的静态导入资产。无需创建凭据或调用模型即可验证页面资源与数据桥接；模型生成和供应商数据可用性仍独立验收。安装验收须检查十一套入口、核心脚本和样式在干净 checkout 可读取。


资产观察安装验收复用既有 macOS Bootstrap 启动步骤，读取全部新增／组合的资产静态模块、样式和固定本地图表库并和checkout逐字节比较，上传 `asset-static-smoke.json` 路径／哈希摘要；资源须进入wheel和实际安装目录。此检查不调用供应商、模型或新作业，也不表示浏览器交互或真实CJPY已验收。

2026-10-23 历史auto/固定来源选择与原始日线校验仅复用已有Tinysoft/Wind/AKShare/BaoStock适配和锁定依赖；三一键入口、requirements/web.in、web.lock、scripts/setup_web.py和Bootstrap无需变更。无新配置或秘密入口；安装兼容性仍由最终同候选macos-14干净安装、固定DSH、3081/8088与Doctor门证明，本机离线链不替代安装CI。

2026-10-23 资产v6封闭部署配置绑定常驻c1a260fa与已合并PR197产品eac68068；仅此配置使用固定ZIP日志读取器，旧恢复合同和严格全账号保全不变。详见[部署合同](research-web-gateway-upgrade.md#资产筹码与精炼布局固定部署v6)。

2026-10-23副图扩展不新增依赖、配置或Doctor能力；requirements/web.in、web.lock、setup_web.py和三个公开安装入口保持。asset-indicator-library.mjs与asset-panel-manager.mjs随原UI包安装，原Mac Bootstrap下载比对追加两模块；固定图表库、许可证、CJPY无凭据待配置、同候选DSH构建/健康检查/Doctor门均保持。


2026-10-23资产副图固定v7部署：封闭apply-assets-v7 / reviewed-asset-observation-v7，PREVIOUS=c4e953c4386c615cde89ad2d014d60c6e2959303，PAYLOAD=3a62ca1a3bff0927db681322a1ff028f08cf03cd（含PR204资产及PR203财务补齐的组合产品）。沿原version4事务、维护锁、BirthFence、64MiB严格业务索引/全账号保全及恢复；额外复用现有市场inflight空闲检查。旧v1–v6、market、模型身份和controller/evidence字节保持。锁文件7c631d4f、严格reader5c3077固定，无新依赖、HTTP、schema或权限；仍须新操作员同候选独评/完整Router/三CI/Mac安装及实际部署证明。

## 2026-10-23：BaoStock盈利能力来源

BaoStock财务扩展复用已批准并锁定baostock0.9.4；没有新增或安装依赖、账号、端口或数据库服务。已核对requirements/web.in、requirements/web.lock、scripts/setup_web.py、三安装入口和Mac Bootstrap；这些文件无需为该适配更改。最终候选仍须同SHA干净Mac安装、固定DSH、3081/8088及Doctor证明兼容，现有服务、正式数据根和外盘不操作。

## 2026-10-23：长期研究档案与机会预警

新增个人 `dossiers/metadata.sqlite3` 使用 Python 标准库且惰性初始化，原文继续使用既有 Store／Snapshots，无新增依赖、端口或服务；安装入口和双运行时选择保持。原 macOS Bootstrap 需核对新增档案／MCP UI 静态资源与候选包字节，并结合固定 DSH、健康检查和 Doctor 绑定最终候选，不能由已有环境替代干净安装。Doctor 的 MCP 配置状态沿现有插件 status；小创缺已核验 Registry 身份时保持 unsupported，无合法安装不开放个人凭据配置。正式恢复、真实凭据／费用与常驻部署另授权，见[保全](research-web-dossiers.md#备份恢复与部署边界)与[候选](research-web-seek-alpha.md)。


档案固定部署使用 `apply-dossiers`／`reviewed-research-dossiers-v1`：前版固定已核验 `5343e18d9f203a87f2d958218e4288afa527711f`，产品固定包含 PR209／PR212／PR213 的已合并主线 `1780064b712afb61ff18f2f1811650fc31fd3038`。复用原 version4 维护锁、BirthFence、Native／RuntimePool／市场及 DataHub 空闲检查、全账号64MiB业务索引与档案保全和恢复；依赖锁、DSH、自动兼容清单、凭据及付费调用保持原合同。源码、CI、实际服务切换和登录后跨会话验收分别留证，未执行的层级不标通过。

WGC 月度吨数解析与资金流时点修复复用既有 HTTP/JSON、可选研究仓与批准锁依赖，无新增安装步骤、包、服务或公开入口；Doctor 既有可选数据库未配置语义保持。隔离 PG 验收不配置正式库，仍要求同候选 Mac 干净安装证明原六安装文件兼容。
