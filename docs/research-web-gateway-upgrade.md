# Mac mini 空私有池网关升级

## 全市场终端固定部署（2026-10-23）

`reviewed-market-terminal-v1`／`apply-market-terminal`固定前版
`0e0022ac792eba88fba0f233524f5c8d66024569`，产品PAYLOAD固定为
`ca20293b8244bb0644bf2039ddd96ee452a27b0b`。该不可变祖先包含终端产品、PIT上游和
已独评的构建器修复f3f4fae；替代先前717暂存检查点。实际部署仍等待PR201与终端最终组合各自合并、
独评和原三CI合格，再核对祖先、完整路径并集、Git blob和文件模式；不提供运行时任意目标或前版覆盖入口。

原version4事务、supervisor/admission维护锁、BirthFence、全账号业务索引哈希与内容寻址恢复继续复用。
研究／历史查询、主实例和网关活动，以及市场GET投影中的`inflight`必须明确为空；未知或活动即拒绝。
terminal沿现有严格业务读取器，业务索引上限64MiB，元数据原1MiB边界保持；旧profile及controller字节不改，
evidence读取器绑定现有v6的`5c3077b7…eebb`，不能用缓存片段替代完整GitHub日志与逐job checkout核验。

固定web.lock为`7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`；
沿原事务仅同步目标锁身份和`code_commit`，恢复时精确恢复原安装清单。本轮不安装新依赖、不启用或迁移数据库、
不改外盘／秘密／Docker，不更换模型。源码仅取自已验证同一common directory下的干净目标checkout，业务数据原位保留。
会话、报告、模型／凭据存储元数据、账号索引以及新增持仓和观察缓存均不得因切换而丢弃；最终实际保全须单独留证。

最终组合必须最新主线资格、独立评审、完整changed-set Router、Project Constraints、Research Web Checks及
同候选macos-14干净安装全部通过，CI证据绑定真实checkout／合并tree与完整日志，不能套用产品或旧工具的通过记录。
本机后端130例、完整操作员测试和预检仅证明各自本地合同；实际切换、双入口健康、认证页面与保全／恢复结果仍待验证，
未获真实回执不标记已部署。Windows/Linux原生及Docker产品验收保留原状态并交接对应设备；本profile不新增运行节点，
现有01／12图保持准确，产品终端的数据流仍以已更新13图为准。


## 华安ETF周报固定部署v2（新目标待授权）

`reviewed-etf-weekly-v2` / `apply-etf-weekly-v2` 固定旧版
`5343e18d9f203a87f2d958218e4288afa527711f`，产品检查点固定 PR209 合并版本
`56709a8dbb6e01d2ab17b64533319e199ebef86f`。v1 的模式、命令与
`988046d23f9951f889a3b9d02e355ed59fd6aa65` 产品身份保留。
用户此前批准的部署目标为 PR208 合并版本 `2e1ba701`；尚未执行 apply 时 master 已前进，
旧操作员的固定产品与 latest master 门不能同时满足，故增加封闭后继，不能跳过 latest 门或沿用旧授权。
**此新组合目标尚待单独明确部署确认；本轮只准备源码与离线证据。**

v2 只增加常量与原分派，沿原 version4 事务、维护锁、BirthFence、主实例和网关、Host/Native/
RuntimePool/市场 inflight 空闲检查、64MiB 全账号业务索引保全及逐阶段恢复。
PR209 已有 `snapshot_dossiers` 将账号档案元数据和引用摘要纳入 `@dossiers` 摘要；
v2 复用该保全路径，不改变 controller、evidence、白名单、权限或保全门。
固定完整日志读取器仍为 `5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb`，
原安装锁 `7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102` 保持，
不安装依赖，不启用周报日程，不产生 Office、厂商或模型调用。

原真实 Git 矩阵验证差异并集、blob、mode、祖先及未知文件拒绝；原全账号索引、活动未知、
阶段中断/回滚矩阵纳入 v2，并补主实例与私有账号真实 dossier 修改后的保全及恢复拒绝。
本机离线成功和旧 PR209 CI 都不能替代 v2 最终候选的独立评审、完整 Router、原三 CI
及同候选 macos-14 干净安装。源码/CI、实际切换、认证页面和正式报告质量分别验收，
未部署状态不得标为常驻已升级或正式周报已通过。

## 华安ETF周报固定部署profile（仅离线准备）

`reviewed-etf-weekly-v1` / `apply-etf-weekly` 固定登记旧版
`5343e18d9f203a87f2d958218e4288afa527711f`，`ETF_WEEKLY_PAYLOAD` 固定PR198真实merge
`988046d23f9951f889a3b9d02e355ed59fd6aa65`。产品reviewed head `61f7d1a6d`的三门已通过，
不代替操作员最终候选的独立验证、评审和CI；切换前再次核定登记旧版。不能通过命令参数
指定任意前版或产品。本轮仅授权源码和离线验证，尚未获得常驻部署授权，未执行apply或切换。

该profile复用原version4事务、supervisor/admission/operator锁、BirthFence、主实例Native/Host
与私有RuntimePool身份/空闲门及全部账号保全恢复；加入64MiB严格业务索引读取与全键摘要，元数据仍
保持1MB上限。Host的真实Future、Wind、报告准备/执行、市场provider关闭/排空以及其他活动或未知
继续阻止切换；profile另显式核对市场inflight为空，不以无研究session替代采集终态。它接受与v6相同的
固定完整CI日志读取器SHA256 `5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb`，
保留每个成功job自身checkout/tree证明，不改变旧profile、controller、evidence内容或自动兼容白名单。

安装清单只更新code_commit并保留原web_lock_sha256；产品锁与已登记安装锁均为`7c631d4f…7102`，
不增加依赖安装/数据库/秘密授权。最终候选仍须共享正确Git common directory、干净checkout、
独立评审、完整changed-set Router及原Project Constraints/Research Web Checks/同候选macos-14干净安装。
部署授权后才按原事务冻结全账号索引、会话/文件/模型配置/账号数据并逐阶段切换与可恢复回滚。
部署后的实际版本、主管理员Native Host绑定、认证页面、保全与真实报告质量另证；离线通过不认证
EDB、真实Office/Wind或正式成稿。对应回归在`tests/research_web/test_model_provider_upgrade.py`，
原全profile真实Git、阶段中断/回滚、全账号保全矩阵包含该mode；API活动见证继续由原`test_api.py`覆盖。

## 资产筹码与精炼布局固定部署v6

`reviewed-asset-observation-v6` / `apply-assets-v6` 固定旧驻留版本
`c1a260fa1d8dcf013426aca938d7e46a98aaee28`，产品为PR197已合并的
`eac6806822294d75da990c751d88ec156a417f62`。后者已通过Project Constraints、Research Web Checks
及同候选macOS干净安装；这不代替部署工具最终候选的独立评审、完整Router和原三CI。

v6复用原版本4事务、全账号索引哈希保全、真实查询/研究空闲检查、BirthFence及逐阶段恢复。
锁文件保持`7c631d4f…7102`，不安装新依赖、不启用数据库、不改外盘或秘密。旧v1–v5、市场及模型配置的固定身份、
controller和旧evidence哈希不变。v6以固定`5c3077b7…eebb`读取器校验实时、完整GitHub运行日志ZIP：
有界下载，成员名称/大小/CRC/完整流、每个成功job的checkout及合并目标tree均须一致；不读取缓存片段或跳过失败门。
原PR192的读取器和严格回归经Git补丁复用，并修复逐job自身checkout缺失不能借用其他job的校验遗漏；未引入其过时v5产品pin。

真实部署必须在两驻留checkout均有目标Git对象、操作员checkout干净且共享正确common目录后执行，
先持锁确认旧版/全账号/空闲，再安装并验证主实例和网关。活动或未知任务存在时延后；完成后验证认证页面与保全，
没有通过时不标记已部署。这里保留历史配置，不能通过运行时参数任意扩展目标或前版。


## 市场限价与历史固定部署（2026-10-23）

`reviewed-market-history-v1` / `apply-market-history` 固定旧版`51f09fa783694aae5234905933948394ca167dcc`、产品检查点`4f0a248fc87249d41e1c3f75f700c17c8351ad95`。检查点为不可变产品祖先，最终组合仍须最新master、独立评审、原三CI和同候选macos-14安装合格。原version4事务、BirthFence、全账号业务索引/会话/模型保全和恢复保持；市场inflight活动/未知均拒绝。旧profile、controller、evidence和自动兼容白名单不改变。

沿现有固定目标锁文件SHA256 `7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`，只同步安装清单该哈希和code_commit；回滚恢复原清单。不安装依赖或启用研究数据库；原已批准主线baostock0.9.4/psycopg3.3.6须实查已安装、pip check及其余版本不变，不能只改清单掩盖缺包。源码来自共享Git common directory的干净目标checkout，业务数据原位不迁移。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-market-history \
  --home /absolute/private-home --source /absolute/qualified-clean-checkout
```

部署与真实认证页另外核对限价/未知覆盖、昨日同当前池逐股金额及资金历史缺口，缺可靠源不冒充补齐。首个合格昨日见证可从当前或上一完整用户缓存恢复，不向生产注入测试样本。Windows/Linux原生与Docker产品验收仍按各设备交接。

组合v5在安装目标产品时，仅把安装清单的`web_lock_sha256`同步为已冻结88ef锁文件的`7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`，并更新code_commit；回滚精确恢复原清单。配置校验只接受原清单或该固定目标清单，不接受任意哈希。用户已授权的三个发行包须先按原锁定哈希安装、核验版本及pip check，并确认其余已装版本不变；不能用更新清单掩盖依赖未安装。旧profile、version4 journal、不可变controller/evidence、账号及业务索引保全不变。

资产 v5 的主实例预检使用已有 `read_business_index`，上限64 MiB，仍拒绝符号链接、非普通文件、越界、损坏或非对象索引。部署元数据继续使用原1 MB读取器；旧资产与模型 profile 的读取绑定不变。真实首次切换因业务索引超过1 MB在停机前被拒绝，旧服务保持；不得裁剪索引或修改不可变证据读取器。修复后须重新通过原评审、三项CI及同候选Mac安装，再执行正式切换和全账号保全。

## 全市场缺口修复固定部署

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-market-gaps \
  --home /absolute/private-home --source /absolute/qualified-clean-checkout
```

最终产品路径与检查点以完整差异并集/blob/文件模式/祖先冻结，只有原操作员、测试和文档例外；不开放任意SHA、附带产品或自动兼容白名单。市场缓存与原会话/数据/模型原位保留；GET市场空闲核验不触发上游。recover只回到固定99d3，继续使用64MiB严格业务读取、原1MB元数据及全账号索引保全。合并后可在既有resident/artifacts/<target>/source内准备同源码common directory的干净detached checkout执行，归档/回收仅针对开发worktree，不回收生产source或恢复包。三个CI及产品实采不替代实际部署/真实认证验收，Windows/Linux产品层仍按设备交接。

## 全市场概览固定版本部署

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-market \
  --home /absolute/private-home --source /absolute/qualified-clean-checkout
```

市场 profile 另将 gateway_upgrade.py 的有界业务读取参数扩展绑定为完整 SHA-256；此文件的额外变化、删除或模式变化拒绝，旧 profile 不获得该例外。业务索引读取使用原64MiB上限，元数据仍为1MB。原现场索引8,673,739字节导致旧 verify_primary/retention/idle 读取失败，修复只复用严格普通文件、规范路径、拒绝链接和JSON对象校验，不裁剪业务数据。

产品祖先、完整路径并集、Git blob 和文件模式逐项冻结；仅操作员自身、测试和文档可随最终工具候选变化。历史 ASSET_MODES 家族包含市场 profile，因而市场切换同样强制业务索引全量保全、资产/DataHub/历史任务及真实 Future 空闲。旧版尚无市场采集服务，切换完成前网关保持围栏；不迁移数据或触发市场/模型查询。recover 根据已验证 journal 的市场 mode 只回到固定 4d2e3c40。部署后以真实登录页核对三个页签、沪深北完整覆盖、来源时间、刷新和原会话/模型保留。

## 资产观察固定版本联合部署

### 资产交互与数据 v5 2026-10-22

封闭profile为`reviewed-asset-observation-v5`，入口为`model_provider_upgrade apply-assets-v5`。PREVIOUS精确固定当前主实例与网关的`51f09fa783694aae5234905933948394ca167dcc`，PAYLOAD在PR188合流及用户当前授权后精确固定完整已合并产品`88ef3817680ac822e2d7c819db845de4b7275173`（包含PR185资产产品9bc4及DataHub研究仓）；旧4d2e、99d3及5495分别属于历史部署合同，不能作为v5当前恢复基线。旧a114候选原三CI全PASS保留为历史，主线前进后须重新认证新组合的本机兼容、独立评审及原三CI／同候选Mac安装，不能用旧树证据替代。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-assets-v5 \
  --home /absolute/private-home --source /absolute/qualified-clean-checkout
```

v5只增加原常量表、previous_for／review_assets及CLI封闭分支；仍逐项冻结固定产品祖先、完整差异路径并集、Git blob和文件模式，未知产品、依赖、workflow或额外字节拒绝。原操作员允许的文档／测试及架构阅读页例外保持，不把它扩成任意部署能力。使用生产venv，从与登记源码共享common directory的干净最终目标checkout执行，实际模块与`--source`一致；不移动开发文件、复制源码或处理凭据以绕过身份门。

沿原version4 journal、维护锁、BirthFence、优雅排空、全账号业务索引冻结与内容寻址恢复；目录后台租约、资产区块／历史及真实Future的活动证明仍由既有产品边界提供，活动或未知时不切换。保留会话、模型配置、账号权限、市场缓存和原始快照，不触发研究、周报、供应商或模型调用。`recover`只按已验证journal的v5 mode返回固定51f09，旧资产v1–v4、两个market profile、模型恢复和不可变controller／evidence保持原合同。

profile和一行读取修复本身没有新增部署节点或HTTP；组合产品包含PR188的可选研究仓／DataHub合同，保留其已审新04数据流，API inventory为321声明／318唯一接口。当前用户明确允许组合验收后随常驻安装已合并锁定baostock0.9.4／psycopg3.3.6，数据库不启用／不迁移、外盘不改；不扩大为任意依赖或数据库配置授权。阅读入口指向已提交组合产品88ef，一行v5读取修复另见8f2cb39a63c99c6e64875daf21dbb8b07518ff43，最终操作员提交另绑。root完成资格、明确空闲、冻结／健康／保全与真实认证页面逐项取证前，状态保持未部署。详见[原profile报告](../.ai/reports/test_report_asset_interaction_v5_deploy_20261022.md)与[读取修复及合流报告](../.ai/reports/test_report_asset_v5_index_fix_20261022.md)。

### Wind工作区 v4（2026-10-22）

封闭profile `reviewed-asset-observation-v4`，入口`model_provider_upgrade apply-assets-v4`。PREVIOUS精确固定`5495e64c0be08c9db58e336705db90584f8ba8b5`，PAYLOAD精确固定PR180真实merge `9b436613aad9136f4959c992c89dd72fc7354ed5`；不能以候选、preview或任意SHA替代。主任务fetch核定真实merge父为08aac/654fa、tree `1aff5360808c835a6096af751e942b6692497bfa`，与候选654fa及preview2e069相同。合并前草稿候选仅保留为历史检查点。

v4承接已合并启动保全修复产品，只改变固定部署身份，不改变原version4 journal、锁、BirthFence、冻结恢复、controller/evidence字节、严格全账号索引保全或依赖/CI。profile v4与journal version4是两个概念，旧v1/v2/v3固定身份、产品范围和恢复语义全部保留。最终仍要求固定payload祖先、完整差异路径并集/blob/模式与干净源码/发布仓库身份，不接受任意SHA或额外产品、workflow、依赖及架构HTML/PNG差异。

旧v3实际切换因启动新增默认三键被严格保全门拒绝，已通过精确SHA还原及冻结的正式recover恢复5495，preserved=true，网关fenced=false。产品三CI39730343750/39730343679/39730452006均PASS；自动门实际checkout2e069，Mac实际checkout654fa6、581秒且安装artifact12405650153已核验。产品Doctor/3081/8088、固定DSH与静态资源通过，CJPY0.5.2未配置时如实不可调用；这些不认证v4操作员最终pin后的本机测试、独立评审、候选CI/安装或实际部署。root完成v4最终资格后才按原授权/持锁空闲/全账号冻结/健康及认证页面合同执行。

最终`recover`须从已验证journal的封闭mode选择v4固定旧版5495；不得更改旧v1/v2/v3分派或恢复包。当前没有新部署节点、HTTP、持久格式或产品数据流，因此不重画图或重新生成HTML/PNG。阶段证据见`.ai/reports/test_report_wind_workspace_v4_deploy_20261022.md`；实际apply只接受最终工具候选完整资格及原空闲/保全门，不以产品通过替代。

### Wind工作区 v3（2026-10-22）

Wind工作区产品PR177已合并后，以新的封闭profile `reviewed-asset-observation-v3` 单独交付部署工具，入口为 `model_provider_upgrade apply-assets-v3`。旧主实例和网关精确固定为 `5495e64c0be08c9db58e336705db90584f8ba8b5`，产品精确固定为 `a0ff3ae2e2ab92bad10ba8547e45027687ec7cc1`；不得用任意前版、目标SHA或祖先替代该产品身份。最终工具候选仍须最新合并基线、独立评审及原三项CI合格；产品原验收不替代本profile工具的候选验收。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-assets-v3 \
  --home /absolute/private-home --source /absolute/qualified-clean-checkout
```

产品范围以固定payload为真源，逐项比较产品/工具目标的完整差异路径并集、Git blob及模式；除本操作员、测试和文档外，不接受新的产品、依赖、workflow、图表HTML/PNG或其他生成物。保持原证据读取器和不可变控制器字节，不扩大任意部署能力或自动兼容白名单。干净checkout、实际模块/`--source`一致、生产venv、源码common directory及两发布角色仓库身份仍按原合同核验。

本轮用户已明确授权常驻部署；只有主任务完成v3最终验收后，才由root持原锁复核研究、日程、私有池、观察、DataHub、历史任务及真实CJPY Future全部明确空闲，冻结主实例和全部账号业务索引，再执行原v4事务及内容寻址恢复。queued/running/cancelling/draining、未知状态或无法证明的witness继续阻止切换；不以HTTP取消代替真实Future结束。该文档任务不执行apply、厂商查询或秘密操作。

`recover` 必须按已验证journal的封闭mode恢复v3固定旧版5495；旧v2仅回9bc12355、旧v1仅回c68814db，模型profile与历史恢复包保持原字节/语义。v3不新增journal版本、部署节点、数据库迁移、HTTP API或产品数据流，现有图与API Atlas无需重画。实际部署前常驻仍为5495；切换后须另核真实主实例/网关版本、全部账号数据保全和认证浏览器页面，不以产品CI或工具预览代替成功回执。

### 既有资产观察 v2 与 v1 合同

新版资产页使用独立的封闭 profile `reviewed-asset-observation-v2`，入口为 `model_provider_upgrade apply-assets-v2`：旧主实例与网关必须同为 `9bc12355c3b80e4e4459f4c250e13fc2634ed23d`，产品精确绑定已合并 PR175 的 `93d62be64084a5c92541a4a008216c0b3f56c2f1`。该产品包含完整指标区、交易／估值摘要、默认折叠的来源表及透明主题图表。最终工具目标仍须为最新已合并、独立评审且原三项 CI 合格的源码版本；产品祖先、完整差异路径并集、Git blob 和文件模式逐项核验，回退后从差异中消失或被删除的产品路径也不能漏检。除操作员自身、文档和测试外，额外产品、依赖或工作流变化继续拒绝。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-assets-v2 \
  --home /absolute/private-home --source /absolute/qualified-clean-checkout
```

从最终工具目标的干净 checkout 执行，`--source` 与实际模块目录必须一致并共享已登记的源码 Git common directory；有未跟踪文件也不符合干净条件。开发主工作区有其他任务文件时，创建受管的干净目标 worktree，不能移动业务文件、修改忽略规则或跳过身份校验。解释器使用原生产 venv；部署前确认两个发布角色仓库已有目标对象，不复制源码目录或凭据。

v2 继续使用原 v4 journal、不可变控制器、锁、BirthFence、优雅排空及内容寻址恢复包。资产／DataHub 终态和全业务索引保全同时适用于 v1、v2；活动或未知任务延后切换。`recover` 根据已验证 journal 的封闭 mode 选择对应固定旧版：v2 只回到 `9bc12355`，v1 只回到下述 `c68814db`。原 `apply-assets` 和模型专项 `apply` 的固定身份、历史恢复包及自动兼容清单均保留。离线检查、CI、实际运行版本和数据保全各自留证，不以预览代替部署验收。

资产专项另固定证据读取器 `evidence.py` 的完整 SHA256，仅允许已审 CI 日志下载30→120秒的有界时限修正；其余命令仍为30秒，日志8MB上限、实际checkout/树、最新三CI和独立评审条件不变。证据文件内容、模式、删除或回退不匹配继续拒绝。该读取器进入原内容寻址恢复包，不修改不可变 controller.pyz 或现场白名单。

资产专项还对主实例及全部私有用户业务 index 的每个顶层值冻结 canonical SHA256，区分字段缺失与空值；journal 不含正文或秘密。前进、回滚、最终完成及 preparing 恢复均核对，变化时保留冻结与恢复记录，不覆盖数据或宣称保全。已结束的 partial 观察和区块可进入空闲，任何 loading 或未知查询状态继续拒绝。

业务索引采用独立的最大64MiB有界读取，校验规范路径、无链接、普通文件与JSON对象；不沿用只适合部署元数据的1MB限制，也不放宽原元数据合同。超过业务上限、损坏或未知路径继续拒绝。

`model_provider_upgrade apply-assets` 仅接受当前 `c68814db170900688d6a799a241efc098eb83f32` 主实例和网关，产品固定为已审 PR171 的 `54d4c8f9421c568de853a2f93263a2bfcd53422c`。工具目标仍须是最新已合并并通过原三项 CI 的精确源码版本；除本操作员及文档/测试外，全部实际差异与固定产品 Git blob、模式一致，固定产品改变过的路径即使从目标差异中消失也逐一核验。未知 UI/后端、依赖、工作流或模式变化拒绝。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-assets \
  --home /absolute/private-home --source /absolute/qualified-checkout
```

仍使用同一 v4 事务、不可变控制器和内容寻址恢复包，不改自动兼容清单、数据根、凭据或 Tailscale 路由。除原 Native、Host、日程与私有池空闲条件，资产观察和 DataHub 查询也须是明确的终态；任何加载或未知状态均延后。回滚及 `recover` 从封闭 profile 决定旧版 c688，不能回退到模型专项的旧版 5df。恢复前复验固定版本身份及原全部保护，不覆盖用户数据。旧 `apply` 的模型专项合同保持原样。

## 模型服务商联合升级

源码权威 `source_common` 与发布角色仓库身份分开：主实例可为独立 clone，网关可为开发仓库的 worktree。
两角色分别记录并恢复校验原 Git common directory/inode 和精确 GitHub origin，源码冻结目录由受审 source 创建。
停机前确认两角色拥有目标 commit；目录、origin 或 inode 变化仍拒绝，不能通过搬迁发布目录或改配置绕过。

工作流完整 blob 只额外允许原定点测试注册与已审 Checks 时限20→30分钟，保留全部测试、runner和检查门；其他工作流差异仍拒绝。已有注册不重复插入，未核对通过的超时或取消不能充作成功证明。
配套有界 workflow 约束 JSON 也只允许同一时限文本20→30；其余必需规则完整保留并逐字节比较，不允许取消约束或任意扩大时限。

五个导航文件始终进入身份检查，即使回退至旧版本而从 `PREVIOUS..target` 差异中消失也不能跳过；单文件或全部回退均拒绝。

导航交付沿同一显式事务：仅 `app/research_web/ui/` 下的 `app.mjs`、`core.mjs`、`intel.mjs`、`shell.mjs`、`workbench.mjs` 改为绑定 PR168 已合并产品 `4e8be6ac7405733755e4a00be10898504e71710a` 的精确 Git blob 与模式；目标必须包含该祖先。其余产品路径仍逐字节绑定 `0d73c034`，工作流及配套约束仅接受上文的定点注册与有界时限变更。任意额外 UI、后端、依赖或文件模式变化拒绝；这不授权任意静态目录更新，不改变自动兼容清单或 v4 恢复合同。源码资格、空闲切换、会话/文件/模型保全和实际浏览器效果分别取证。

显式入口 `research_workbench_entrypoint.resident.model_provider_upgrade apply` 针对原主实例与网关
`5df8e17e04f1b588f7e742423d81fb8e0ba34cb2`，只允许已审模型服务商产品
`eb42682f22ab9629bfd5f677d8ed38ae0d0ebec0`、已合并登录外观 PR166
与已独立审查的 PR168 导航界面；模型核心固定基线为 `0d73c0348094f11c3440d8f6893c7a6896a8dbc8`，
五份导航文件固定为 `4e8be6ac7405733755e4a00be10898504e71710a`，另含该操作员及测试/文档变化。
自动兼容清单、固定 DSH、依赖及原 controller.pyz 不修改；目标必须是最新已合并且三项 CI 合格的精确 SHA。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply \
  --home /absolute/private-home --source /absolute/qualified-checkout
```

从合格源码目录执行，解释器须为生产 venv。在发信号前安装独立内容寻址恢复包和 LaunchAgent，
冻结原 wheel、配置与完整保全摘要。服务商/模型与凭据是否已配置只取元数据，不记录 Key 或问题正文、不调用模型。

持 supervisor/admission/operator 锁；Native、Host、自动化及全部用户池中任何活动/未知均等待。
先写 version 4 全请求冻结意图，再取得 BirthFence；部分 stage/owner/releasing 中断由原身份恢复处理。
确认原私网根返回 503 后才写旧控制器可读的主实例 journal，随后优雅排空网关及停止主实例。
原控制器模块真实摘要绑定 Git `02c086b168e62723887c7a778f716f6146595b6d`，恢复期间其私网根健康不可能通过，
因此不会提前撤门；旧控制器可先恢复原主实例，新恢复任务须重新核对空闲并协调两端。
不改 Tailscale 路由，原 `/collections` 保留，不强杀、不停运行研究。

两端源码/wheel、网关绑定及实际 revision 一致，健康、保全和模型元数据全部通过才记录 accepted/baseline 并撤门。
切换失败自动恢复原两端；排空/活动未知保留 journal 等待。终态写入、unlink 或 fsync 异常返回
`completion_unknown`，当前调用不再停机回滚；独立恢复重新验证身份并取得全部保护后处理，栅栏已撤则不执行恢复。
恢复只还原部署配置，不覆盖账号库、会话、模型凭据与业务文件。

日志：`logs/model-upgrade.log`；私有回执：`server/run/model-upgrade-result.json`。
离线故障注入和 CI 不替代实际部署后检查；活动或状态未知期间不得宣称部署完成。

恢复LaunchAgent仅在自身EnvironmentVariables声明系统/Homebrew PATH；安装恢复包前用同一路径运行既有Git LFS版本检查。缺少工具在栅栏、journal和信号之前失败，不安装包、不禁用Git钩子、不修改全局PATH。SIGTERM优雅等待延至90秒；超时仍保留recovery_required，不强杀。旧恢复包和任务保持原样，新版本使用独立内容身份。

## 保留主实例版本的静态网关更新

主实例无需更新研究进程时，显式使用 `apply-ui --preserve-primary`，`--primary` 固定实际主实例 SHA，
`--target` 固定已合并、资格通过的新网关 SHA，`--expected-gateway` 固定旧网关 SHA。
这与默认 `apply-ui` 的 primary=target 合同分开；不扩大自动兼容白名单，不安装或切换主实例。

注意：主账号的 `/` 和 `/static/*` 仍取自主实例的 UI 目录，因此此模式不能单独交付主账号的侧栏等完整壳更新。
需要完整更新主账号界面时，应先使用下节 `stage-primary-ui`，由原 resident 完成受控切换，再更新网关；
不能把网关 revision 更新或旧菜单适配当作主账号已加载新侧栏的证明。

version 3 / `static-gateway` 事务同时检查 primary→target、旧网关→target、target→tool 的祖先和完整 blob。
前两段仅允许 UI、文档、测试、报告和确切的升级器模块；升级器 blob 必须等于经过资格认证并冻结的工具 blob。
最后一段只允许升级器模块、文档、测试和报告。后端、依赖、控制器或任何未知路径变化均拒绝。
升级器是显式操作员模块，业务运行时不导入它；上述合同保证运行时后端保持一致。

恢复包支持独立的 version 3 身份、三段离线 blob 验证和原主实例 SHA；v1/v2 helper 不接管 v3 journal。
原锁、空闲/私有池检查、恢复包先安装、优雅排空、保全和回滚均继续执行。工具与目标资格均独立核对。
旧主实例的已有菜单由网关适配身份链接，复用原交互控制器，避免重复菜单或重复退出监听。

## 显式准备主实例 UI 候选

当已合并的 UI 更新同时包含本升级器自身时，自动 resident 仍拒绝该路径。先从精确目标的干净工具 checkout、使用原主实例解释器执行：

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.gateway_upgrade stage-primary-ui \
  --home /absolute/private-home --source /absolute/reviewed-target-checkout \
  --primary EXACT_CURRENT_PRIMARY_SHA --target EXACT_VERIFIED_MASTER_SHA
```

此命令只准备新旧 wheel 和私有 candidate，不停服务、不更改自动白名单、baseline 或 controller.pyz。
它核对同一 Git common directory、工具实际路径、解释器、原 manifest 与源码、隔离候选、最新主线及原三项 CI；
拒绝 primary/gateway 恢复 journal、其他任务尚未接受的候选和准备期间的候选替换。
只允许 UI、文档、测试、报告及本升级器一个精确 Git blob；已有已接受的旧候选可退休，同一审查身份可重复校验。

随后执行原 `rwb resident tick`（或等待已安装监督器）：原不可变控制器仍持准入/lifecycle锁、检查原生/Host/排队自动化空闲，
写 journal 后才切换，失败仍恢复旧 wheel 与源码。必须确认 accepted、实际进程 revision 和会话/模型保全后，才能继续下述网关 `apply-ui`。
主实例已到目标时跳过准备；活动或未知保持 deferred，不强停。现场不可变控制器须先独立核对支持复用同一 previous/target candidate。

## 已验收界面的显式更新

当主实例已自动更新而网关仍使用旧界面时，用`apply-ui`更新网关。工具版本与产品版本分开认证：
工具checkout须为最新已合并、独立评审及三CI通过的提交；`target`须等于当前primary且独立通过原资格核对。
旧网关到产品只允许UI、文档、测试与报告；产品到工具只允许升级器自身及文档、测试、报告。
两段差异均核祖先和完整路径/blob，禁止用rename隐藏后端删除；依赖、未知后端及控制器变化拒绝。

产品段也可包含本升级器自身，但其完整 Git blob 必须与冻结工具版本中的同一路径完全相同；
不接受缺失/删除或与恢复工具不一致的 helper。该判断随 version 2 恢复包冻结，离线恢复再次执行同一校验，
不会把一段临时内存放行逻辑冒充持久恢复合同。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.gateway_upgrade apply-ui \
  --home /absolute/private-home --source /absolute/reviewed-tool-checkout \
  --expected-gateway EXACT_OLD_GATEWAY_SHA --primary EXACT_CURRENT_PRIMARY_SHA \
  --target EXACT_CURRENT_PRIMARY_SHA
```

命令须从已审工具checkout运行；业务网关只切换到产品target，工具源码不写入主实例或业务checkout。
自动兼容白名单、既有控制器与version 1/固定旧primary恢复合同保持。新模式使用version 2 journal，
记录两份资格证明、逐路径blob及工具身份；旧helper在任何进程/源码/配置/slot操作前拒绝version 2。

新版恢复pyz从工具Git对象构建，使用内容寻址路径与独立LaunchAgent，不覆盖旧artifact/job。
恢复核对自身身份、manifest/Git blob、目录和共同Git身份、两段离线差异及实际primary；不要求在线GitHub，
也不依赖工具checkout继续存在。当前master、其产品/网关祖先及不可变恢复包在事务结束前必须保留。
恢复成功后仍只回退网关源码和匹配绑定，不回写会话、附件或模型设置。

全部原supervisor/admission锁、出生栅栏、SIGTERM身份/排空、完整保全及journal先落盘的门继续执行。
发信号前活动/未知返回`deferred`；发信号后尚未退休或恢复未完成返回`recovery_required`并保留journal，
不能当作部署成功，也不得升级到强杀。

## 既有管理平面专项

这是显式操作员入口，不扩大 resident 自动兼容清单，也不修改原 controller.pyz、安装基线、主实例 wheel 或研究引擎。当前受审产品基线固定为 `6c4ac79bcf03fb36ffbe9c1c40a647b8e8a34556`；目标相对此基线只接受列出的管理平面源码及文档、测试。其他产品变化必须重新专项审查。

```bash
python -m research_workbench_entrypoint.resident.gateway_upgrade apply \
  --home /absolute/private-home --source /absolute/reviewed-checkout \
  --primary 6c4ac79bcf03fb36ffbe9c1c40a647b8e8a34556 --target EXACT_MERGED_SHA
python -m research_workbench_entrypoint.resident.gateway_upgrade status --home /absolute/private-home
```

`apply` 校验同一 Git common directory、干净源码、最新 merged master、受管独立评审和三项实际树匹配的 CI。主实例 supervisor/admission 独占锁覆盖整个操作；Native、Host、自动化任一活动或未知都延后。任何私有 owner、auth/key、未知控制记录、相关子进程或孤儿进程也延后，不强停研究。

首次升级持 SQLite `BEGIN EXCLUSIVE`（仅查询、最终 rollback），覆盖全部账号且拒绝 WAL/hot journal；对每个空 owner 槽位先登记暂存目录 inode，再用 macOS `renamex_np(RENAME_EXCL)` 原子占槽。已有原生 owner 永不覆盖。出生栅栏不能代替 HTTP 排空。

普通 SIGTERM 等待 uvicorn 完成已接纳请求和线程；超时保留 journal，不升级为 SIGKILL。重复信号只允许经过版本、handler 源码摘要及默认无强制超时合同核验的 uvicorn 0.53.0；未知版本拒绝。旧 PID 完全退出后才移除 launchd job；KeepAlive 替代进程不能穿过仍持有的 SQLite 锁。

目标网关在 `server/run/gateway-upgrade.json` 存在时拦截全部业务 GET、登录及控制请求，只开放廉价健康端点。排空后才释放旧出生栅栏，再启动冻结目标。目标健康、当前 primary 绑定和会话/模型配置/账号库保全全部通过后才移除 journal。

SIGTERM后只以PID消失确认退休；zombie或签名变化继续等待且不追加信号，超时延后。完整保全journal专属上限16 MB，发首个信号前核对实际JSON UTF-8字节并预留4096字节phase余量；专属reader以同一私有fd核对身份、长度、时间及当前路径，拒绝替换、短读或超限。配置通用reader仍为1 MB。

失败恢复旧网关源码和与当前主实例匹配的绑定；原失配配置另留审计，不能当作健康回滚。恢复先写 rolling_back 再切源码与配置；preparing 阶段崩溃只撤销本事务空槽，不发信号。恢复不覆盖业务文件或凭据。独立不可变 recovery.pyz 和 LaunchAgent 在停机前安装，崩溃后按同一 journal 恢复；活动、身份不符或状态不明仍延后。

证据在私有 `server/run/gateway-upgrade-{original,result}.json` 和 `logs/gateway-upgrade.log`。不记录问题或回答正文，不触发模型调用。源码、模拟测试、CI和真实部署结果分别报告。


2026-10-23资产副图固定v7部署：封闭apply-assets-v7 / reviewed-asset-observation-v7，PREVIOUS=c4e953c4386c615cde89ad2d014d60c6e2959303，PAYLOAD=3a62ca1a3bff0927db681322a1ff028f08cf03cd（含PR204资产及PR203财务补齐的组合产品）。沿原version4事务、维护锁、BirthFence、64MiB严格业务索引/全账号保全及恢复；额外复用现有市场inflight空闲检查。旧v1–v6、market、模型身份和controller/evidence字节保持。锁文件7c631d4f、严格reader5c3077固定，无新依赖、HTTP、schema或权限；仍须新操作员同候选独评/完整Router/三CI/Mac安装及实际部署证明。


## 研究档案固定部署（2026-10-23）

档案固定部署使用 `apply-dossiers`／`reviewed-research-dossiers-v1`：前版固定已核验 `5343e18d9f203a87f2d958218e4288afa527711f`，产品固定包含 PR209／PR212／PR213 的已合并主线 `1780064b712afb61ff18f2f1811650fc31fd3038`。复用原 version4 维护锁、BirthFence、Native／RuntimePool／市场及 DataHub 空闲检查、全账号64MiB业务索引与档案保全和恢复；依赖锁、DSH、自动兼容清单、凭据及付费调用保持原合同。源码、CI、实际服务切换和登录后跨会话验收分别留证，未执行的层级不标通过。

操作员必须从受审、干净、同候选三CI合格的最新已合并master执行；目标完整差异路径并集、blob及模式必须匹配上述产品，仅允许操作员自身与文档／测试变更。原证据读取器摘要固定；任意额外产品变化拒绝。先验证恢复包和所有业务状态，锁内再次核对前版与明确空闲，未知／忙碌延期，失败沿封闭profile恢复同一5343前版。不得直接运行其他profile或改写现场白名单。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.model_provider_upgrade apply-dossiers \
  --home /absolute/private-home --source /absolute/clean-reviewed-tool-source
```

没有新服务、HTTP、依赖或第二研究引擎，现有图与API Atlas拓扑保持。实际验收需登录私网页面，验证五区、冻结交接与第二会话、原业务索引及全部账号保全；只用离线NativeFixture的证明不能提升为真实模型质量。收费MCP、秘密录入与生产持续跟踪不由本入口授权。


恢复依赖保全：新恢复包manifest绑定永久`resident/artifacts/<target>/source`，与journal的target/source/pyz摘要一致后，且源路径无别名、属主正确、Git checkout干净，才在父恢复进程导入app之前加入sys.path。不得设置PYTHONPATH传给旧服务；旧wheel不含档案模块时仍用冻结源进行档案索引核对。新DOSSIERS/ETF-v2包缺source拒绝，历史旧模式manifest和旧pyz字节保持原兼容。保留该冻结源直到恢复结束；缺失或篡改保持围栏并记录错误码，不跳过档案保全。

## 今日发现组合固定部署（2026-10-23）

用户已明确授权组合部署今日发现、ETF配置和持续研究仓；封闭`apply-discovery` / `reviewed-discovery-v1`的PREVIOUS为`5343e18d9f203a87f2d958218e4288afa527711f`，PAYLOAD为`1780064b712afb61ff18f2f1811650fc31fd3038`。复用原version4事务、BirthFence、全账号业务索引/档案/模型保全与恢复；旧profile及controller/evidence身份不变，无新依赖、迁移或外盘操作。

新mode在任何后端HTTP/启动前重复只读检查primary和全部私有账号的automation/discovery元数据及report-workflows/catalog.json；任何启用任务/日程、活动或未知执行、损坏结构、别名路径均延后。缺失目录/目录中的catalog按原运行时无计划语义处理，绝不请求账号后端来证明空闲。该门也适用于恢复，不修改原同意、计划或数据。不存在模型调用或启用生产跟踪授权；现场切换、认证真实页面及全账号保全另留证。
