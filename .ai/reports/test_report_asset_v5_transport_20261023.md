# 资产v5完整CI日志传输修复：验收草稿

日期：2026-10-23。宿主：macOS Mac mini。任务类型：Web功能／固定部署工具修复。任务`asset-v5-transport-20261023`，基线和当前固定产品为最新master／PR189真实merge `5d3927fae923d443a2c85431e4bc6ec33be7c9f6`；PREVIOUS仍51f09，Web锁仍7c631d4。当前未部署：主实例与网关仍51f09，本任务未停服务、无journal，最终候选、独评、原三CI／同候选Mac安装及实际切换由root分别绑定。

## 故障与范围

正式qualification读取约4.5 MB raw job日志时多次120秒超时；一次raw106.66秒，HTTP1也迟。先前gh run view探针为1.58秒、24436行及同checkout55cf，raw／CLI为4,496,420／5,499,750字节；现确认官方2.67 Scanner存在64KiB行限制，会静默截断并缓存，因此这些计时／行数／checkout不能证明完整性。f853方案已拒绝，不提交；原稳定探针记录仍保留于Git common directory的`leon-engineering/deployments/asset-interaction-20261022/job-log-archive-producer.json`，不改写其原结果或继续作为成功验收。

新机制为fresh `gh api repos/REPOSITORY/actions/runs/RUN/logs`取得二进制ZIP，严格校验并读取完整job成员，不经过行扫描或使用缓存裁剪结果。主任务新下载实测2.76秒／362044字节，样本含`0_checks.txt`4496420字节及`checks/system.txt`605字节；这是传输检查点，最终完整性与ZIP安全仍需源码回归及独评。原120秒、资格预算和fresh workflow／成功job／当前已合并PR／head SHA／checkout／目标tree门不得放宽，下载与解压需有界且失败关闭。本轮不修改不可变controller.pyz及module，不回写旧恢复包。

旧`ASSET_EVIDENCE_SHA256`保持`ec022e39a89a3dbd021fca26049342ce149077f5beb62a8df2aba7826d016d25`，旧profile仍要求旧reader。新`ASSET_V5_EVIDENCE_SHA256=22d8dde6266096cec77b0fb3ce5e27d3f05e52bef4fcdc747bed5289f00d4679`，reader已格式化固定并读回SHA相符；原f853文件虽曾读回匹配，机制缺陷已使该接受结论失效。固定产品5d3927、PREVIOUS51f09与Web锁7c631d4保持，没有任意SHA、依赖或恢复豁免；当前源码全套回归已通过，最终候选提交／CI仍由root另绑。

主任务已核实同一fresh Bootstrap runs API在默认无header时持续返回0，显式`-H 'Cache-Control: no-cache'`的一次shell／Python对照返回正确run39803484507。该header只请求HTTP重新验证，不保证API可用；带header仍偶发返回0，瞬时空响应继续fail closed，保留resident_ci_missing，不增加重试或缓存fallback。API元数据与ZIP均显式请求重新验证，新reader22d8哈希已读回匹配，新增header后的5模块完整回归1156 PASS／136.74秒（1项Starlette弃用警告），最终候选提交／CI仍待绑定。

主任务以新reader真实qualify已合并276，三个workflow的checkout55cf及tree一致，单次qualification PASS，证据为logs/asset-transport/fresh-qualification.json；这不把先前resident_ci_missing失败改为PASS，也不认证尚未提交的transport候选CI或保证下一次GitHub响应可用。

加header前的ZIP阶段已覆盖selected member实际compressed span的有界DEFLATE到EOF、actual长度／CRC／UTF8和尾随拒绝，以及STORED／DEFLATE forged-prefix与symlink反例；当时test_resident.py 86 PASS、独立边界12／12 PASS，完整回归1155 PASS／133.71秒。上述结果保留旧字节归属，不认证加header后的22d8版本、最终候选CI／Mac安装或实际部署。

当前22d8字节的源码验证已完成：5模块1156 PASS／136.74秒，1项第三方Starlette弃用警告（logs/asset-transport/final-combined-tests.log）；四文档JS112 PASS／0 skip（final-documentation-tests.log）。主任务另确认changed4py的ruff／black／isort PASS、2source mypy PASS、GitSafety fsck PASS，以及最终22d8字节独评APPROVE；上述结论各按其范围记录，不扩大为全项目静态检查或资源清理完成。正式candidate SHA及新候选CI／Mac安装／部署仍由root绑定。

## 原证据与未完成项

| 验证层 | 事实／边界 |
| --- | --- |
| 旧产品／候选CI | 主任务已核定PR187真实merge276491c9及9a9候选原三CI全PASS；不转写为本transport候选通过 |
| 依赖安装／Web锁版本 | 用户已批准的三个发行包已由主任务安装，95个适用Web锁包精确，旧已装版本无变化；本轮文档不安装包 |
| 全局pip check | FAIL，保留11项旧legacy缺失；不能写成全局依赖健康 |
| Web-only安装合同 | setup_web.py既有合同先检查Web闭包，再以--no-deps安装保留legacy元数据的root分发；本次不改安装器、锁或豁免，不为旧可选栈补包 |
| 当前22d8源码回归／独评 | 5模块1156 PASS／136.74秒／1 warning，4文档JS112 PASS；最终22d8字节独评APPROVE，由root确认，正式候选SHA仍待绑定 |
| 新候选原三CI／Mac安装 | NOT_RUN／待最终提交；原Project Constraints、Research Web Checks、macos-14干净安装／DSH／3081／8088／Doctor门保留 |
| 实际部署／认证页面／数据保全 | NOT_RUN；仍51f09，未停机、无journal |
| 数据库／外盘／跨平台 | 不启用或迁移DB、不改外盘；Windows／Linux原生与Docker产品本任务未执行 |
| 筹码Wind原型 | 属root独立隔离任务，2262日换手率采集证据不作为本轮UI／算法改动，本profile不夹带原型 |

## 变更与文档映射

| 源变化 | 回归与文档 |
| --- | --- |
| GitHubEvidence.qualify fresh二进制ZIP严格读取 | test_resident.py；部署合同、架构01–05、安全与本报告；截断／缓存的f853方案已拒绝 |
| 仅v5的新reader哈希／PAYLOAD5d3927 | test_model_provider_upgrade.py；README、四字段readme-review、开发映射、安装／平台／多用户边界 |
| 官方阅读源码链接 | architecture-map只固定已提交产品5d3927，321声明／318唯一HTTP及图源保持；transport最终代码提交另绑 |

已核对requirements/web.in、web.lock、scripts/setup_web.py、research-web-installation.md和research-web-bootstrap.yml；依赖、安装器和workflow与基线字节不变，安装说明补本轮真实状态。文档本地完整changed-set Router／constraints／doc-sync、官方生成检查及相关文档回归据实际执行另记`logs/asset-v5-transport-docs/`，不提前认证PASS。正文和读者链接指向已合并产品5d3927，尚未提交的transport修复不伪装存在于该产品提交。

## 原CLI方案文档检查点（不认证ZIP方案）

| 检查 | 实际结果／证据 |
| --- | --- |
| 完整Router／约束 | 完整26路径；Git绑定plan v4为L4，保留unknown-boundary并按现有catalog补选原三CI；constraints 0 violations。logs/asset-v5-transport-docs/router-bound-plan.json、constraints.log；提交后仍须绑定最终候选 |
| 文档同步／治理 | doc-sync、806文件governance及官方Python索引check PASS。logs/asset-v5-transport-docs/doc-sync.log |
| Router文档JS闭包 | research_web_architecture、documentation_governance、actions_quota_governance、repository_cross_platform_contract四模块112 PASS／0 skip。logs/asset-v5-transport-docs/router-documentation-tests.log |
| 文档HTTP／同步回归 | test_documentation.py与test_doc_sync.py共29 PASS，1项第三方Starlette弃用警告。logs/asset-v5-transport-docs/python-documentation-tests.log |
| 官方生成物 | Atlas／阅读页只固定产品source5d3927，321声明／318唯一HTTP，官方check PASS；Python索引官方重生成字节不变，全部图源及图HTML／PNG不改。logs/asset-v5-transport-docs/atlas-preview.json、atlas-check.log、pyindex-preview.json |

上述PASS属于原gh run view机制说明阶段的本机文档范围，不认证ZIP源码、候选CI、全局pip check或实际部署。旧handoff中接受f853的结论已失效，ZIP及加header前的交接保留原归属；当前22d8 reader哈希已固定并读回匹配，本次三文档与必需门结果另存revalidation-final-handoff.json。新header后1156项完整回归与最终字节独评已通过，正式候选提交及原三CI仍待root绑定，原失败、旧产品／CI及锁版本证据保留。

本轮文档不修改源码、测试、CI、依赖、服务、凭据或旧恢复包，不执行Git提交／发布、厂商／模型调用或线上qualification。图源和产品HTTP／数据流无新增，不重画架构图；日志传输取证、候选资格和实际部署分层记录。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"本修复在现有Native资格服务内fresh下载二进制ZIP并严格读取job日志，拒绝行截断与缓存方案，原120秒、资格预算及workflow／job／PR／checkout-tree门不得放宽；没有新进程、部署节点、HTTP或业务数据流，旧profile和冻结恢复包保持，01及12图准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"仅v5最终绑定受审ZIP reader与已合并产品5d3927，不改变主实例／网关、账号角色、凭据namespace、BirthFence、空闲或全账号保全；旧profile／controller／恢复包保持，拒绝的f853不取得部署资格，二进制日志解析不新增用户数据路径，01／12图无需更新。","diagrams":[]} -->
