# 资产观察常驻部署合同与现场验收

任务 `asset-observation-deploy-20261021`，宿主 macOS / Mac mini；Web 功能部署。用户明确授权部署已合并的 PR171。当前状态：CONTRACT_IMPLEMENTED_DEPLOYMENT_NOT_RUN。

现场只读确认主实例、网关和 accepted 为 c68814db，无主实例或网关恢复 journal。原显式操作员仅支持旧 5df→模型专项，不能交付本次新增资产后端；未调用旧模式停机或修改现场白名单、baseline、数据和凭据。

## 精确范围

在同一 model_provider_upgrade 操作员增加封闭 apply-assets 模式：旧版固定 c68814db，产品固定 PR171 合并的 54d4c8f。目标仍须是最新已合并、独立审查且原三CI合格的工具源码；除操作员、测试和文档外，逐路径匹配固定产品 blob 与模式。固定产品改变的路径即使回退后从 diff 消失也必查，未知后端、UI、依赖或工作流继续拒绝。

复用原 v4 前进/恢复、不可变 controller、独立恢复包、supervisor/admission 锁、BirthFence、安装 lease、优雅排空和数据/模型保全。恢复依据已验证 profile 的 c688 旧版，旧 apply 模型合同保持。资产观察和 DataHub 查询非终态也阻止停机，不以 Native 空闲代替。

不新增依赖、运行服务、数据库、模型调用、公共网络或 Tailscale 路由；不复制工作区源码覆盖发布目录，仍以 GitHub 为唯一源码来源。Windows/Linux 产品原生部署保留 NOT_RUN。

## 实际执行

- 新增合同回归首先观察 AttributeError 红灯，日志 logs/contract-red.log。
- 整模块最终184项 PASS，包括真实临时Git正反例、模式/依赖/回退/删除/非祖先拒绝、双profile真实操作方法与各恢复阶段、原不可变控制器及独立发布clone身份，日志 logs/contract-final.log。
- 现场预检发现两个私有业务索引超过通用部署元数据1MB限制；新增独立64MiB有界业务读取，不放宽原元数据合同。先复现大索引拒绝，再覆盖大于1MB成功和超限/链接/损坏/非对象拒绝。修正后只读保全预检成功：主63个会话、1个资产观察、12个私有索引，均无恢复journal；未停机或调用供应商。原候选CI不能替代修正候选，按受管repair重新验证。
- 复审补充FIFO会先阻塞open、到不了fstat：使用O_NONBLOCK后再检查普通文件，受控子进程3秒超时的FIFO负例通过；不改普通文件读取语义。原候选保留，不以旧CI替代最新修正候选。
- 独立评审发现原会话快照未覆盖业务索引：新增资产专项主实例及全部私有用户 index 每个顶层值的 canonical SHA256，区分删除、空值和修改；prepare 冻结、journal 形状校验及 verify/finish/preparing recovery 复核，不覆盖数据。新增丢失/变更负例和 verify/finish 故障保持冻结回归。已修正合法 partial 区块误判忙碌；loading 仍拒绝。原快照和旧 profile 不变。新测试先观察缺少新函数及 partial 拒绝的红灯，日志 logs/preservation-red.log。首次命令遗漏 Web 独立测试 confcutdir，因根 legacy conftest 缺少 sqlalchemy 无法收集；按既有独立入口重跑，未安装新依赖。
- 本机只读索引检查：1个既有partial观察，7个区块均为明确终态，6个已完成和1个失败DataHub查询；没有启动供应商或模型调用。真实停机前仍必须由操作员重新核对，不能复用本次快照作为准入。
- 同候选 CI、正式切换、保全摘要、实际浏览器与新版本读取尚待完成，不能据离线回归认证已部署。

## 安装与文档

requirements/web.in、requirements/web.lock、scripts/setup_web.py 和原 Mac Bootstrap 无须更改；只有本项目操作员及测试/文档变化。干净安装兼容由同候选 Mac CI证明，不依赖本机额外包。原已注册回归模块继续进入同一 Checks步骤；新增65项预留15秒，不增job、runner或超时。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"资产部署只为既有联合操作员增加封闭固定版本profile，继续使用原主实例、网关、不可变控制器与恢复包；未新增运行节点或改变唯一DSH执行拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原私有池、BirthFence和全请求冻结保留，新增只读资产查询终态证明，不改身份、用户根或业务持久化合同，现有会话及凭据仍按同一保全链核对。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在原注册部署回归模块增加固定版本及恢复负例，复用原Checks和Mac Bootstrap，没有新增job、runner、依赖、模型调用或其他平台产品派发。","diagrams":[]} -->
