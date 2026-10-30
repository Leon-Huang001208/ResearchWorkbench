# 专业 Agent 协作 MVP 实现与验证记录

> 任务记录：本文件记录当前未完成验收的候选，不是生产就绪声明。

## 身份与授权

- 宿主 macOS，Web 功能开发；本平台目标 Native／Mac Docker Desktop。Windows/Linux 产品验证 NOT_RUN。
- 基线 `1be480183187f181dbcee486d943aabb3559c9d5`，分支 `codex/specialist-collaboration-20261028-specialist-collaboration`。
- 原 checkout 出现 dataless 文件和未知归属的过期安全锁；未删锁、未覆盖源码。从同一已核验 GitHub remote 建立干净隔离 checkout，通过 git_safety fsck 后由正式入口建立 worktree。
- 用户授权仅创建 PR，不合并、不部署；真实模型调用须先估算并确认总费用，本轮没有调用。

## 已实现候选

- 四类不可变专业角色，冻结现有能力中心 Skill 版本、编译摘要及资源清单；独立子上下文，实际原生方法读取另行核验。
- 动态 DAG、依赖与修订校验，输入变化和证据版本变化使下游失效；私有账号账本保存计划、尝试与调用身份，不保存第二份聊天正文。
- 原生 continuable 子会话与持久 reserve／dispatch／accepted 阶段；取消请求不冒充终态，未知提交不重放。支持明确续跑及历史见证对账。
- 每个原生模型请求的 Agent/turn/step 去重、预算准入和截止约束；缺失用量保留未知。按时完成的资格冻结，不随查看时间到期。
- 现有界面的显式协作、未确认预算、节点状态、部分成果和明确续跑；最终接受仍由原报告质量链与专项否决共同控制。
- 原有 Checks／Mac Bootstrap 步骤追加专项回归、模块导入和单个新UI模块字节核验，没有新增依赖、runner、job或延长超时。

## 实际验证

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 干净 source checkout 的 Git fsck／无锁检查 | PASS | git_safety check 实际回执；未修复原 checkout |
| 新 checkout Harness 初始化、隔离分支 | PASS | 正式 Harness 与 git_safety delivery start 回执 |
| Node 24.19.0 专项及邻近界面测试 | PASS | 106 passed，0 failed，0 skipped；`logs/specialist-final-focused-node24.log` |
| 文档治理目标回归 | PASS | 8 passed；`logs/specialist-doc-governance.log` |
| JS 全量首轮 | FAIL | 1540 passed／4 failed／1 skipped；`logs/specialist-all-javascript.log`。文档缺链已修复并重验；其余3项缺项目 Python 环境 |
| Python 编译与 diff whitespace | PASS | compileall 与 git diff --check 实际 exit0；不是行为测试 |
| Router | 已规划 L4 | `logs/specialist-verification-plan.json`，受管 manifest 14项摘要已核对；候选尚未提交，最终SHA必须重新绑定 |
| Python pytest／ruff／black／isort／mypy | BLOCKED | 已有环境缺 pytest，原依赖部分 dataless；旧归档环境也不完整。未安装或修补未经批准的依赖 |
| Native／Docker 产品与浏览器整合验收 | NOT_RUN | Python 验证环境尚未具备，不用离线JS替代 |
| GitHub 原三门／同候选Mac安装 | NOT_RUN | 未推送，未创建PR，未进行跨平台dispatch |
| 真实模型、取消及重启小样本 | NOT_RUN | 费用授权关口未开启 |

## 审查与修复

已进行独立 Python／JavaScript 和界面接入审查。发现并修复：专项否决被末尾接受逻辑覆盖、取消首次发送锁竞争、父任务停止后的恢复接线、已完成结果随deadline过期、证据同ID覆盖导致旧结论复用、Skill只声明未实际传入、reserve到dispatch的崩溃空窗，以及取消该空窗时丢失提交阶段。修复后的 Python 行为测试尚未执行，不据静态修复宣称这些平台行为已验证。

## 费用与剩余工作

离线代表性首个请求至少需要48613保守预留单位，未含全部实际历史；新界面未确认默认200000、12次请求，旧已确认草稿保留原值。预留单位不是精确Token或人民币费用上限。真实小样本仍须按实际选择的模型、当前官方单价、请求与故障场景测算，再确认总费用。

当前保留源码 worktree 和分支。须获准在任务隔离环境安装仓库声明的Web依赖及测试/静态工具，完成Python与L4实际闭包、最终独评、Native/Docker和适用CI，再创建待审PR；不自动合并或部署。该状态为 BLOCKED／未完成验收，不是 cleaned 或交付完成。

## 依赖授权后的验证更新

用户已明确同意在本任务独立虚拟环境安装依赖。已安装哈希锁定Web依赖及已批准测试/静态工具，pip check通过，未修改产品依赖声明或全局环境。

- 专项Python首轮78 passed；原生控制入口补充后API模块7 passed。
- 相邻Python回归496 passed、2 skipped、1 failed；失败为旧工具目录精确集合缺少本次四项新工具，已更新集合并定点复验1 passed。未将整轮重写为全部通过。
- 完整JavaScript1544 passed、1原有条件skipped、0 failed；日志specialist-all-javascript-validated-env.log。
- 专项及改动集成文件Ruff通过，Black/isort检查通过；mypy专项7源码文件通过。
- 当前不再受测试依赖安装阻断。完整L4、本平台Native/Docker、最终评审和远端CI尚未完成；未创建PR、未合并、未部署、未执行真实模型。前述BLOCKED安装记录保留历史归属，不代表当前仍需重复安装批准。


## 当前合并与部署授权

用户已明确要求完成验收、合并和部署；替代早期仅PR交付约束。部署仍须真实空闲、身份、全账号保全与恢复，active=null拒绝。独立真实模型样本仍须先确认费用上限。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "专业协作仅在原FinGPT模式选择和会话内增加预算及状态投影；布局模块分离，沿既有详情和消息生命周期，没有新增工作台或浏览器执行循环。", "diagrams": []} -->
<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "新增四个专业协作HTTP入口与私有账号账本，Host校验DAG和预算；现有Host→私有桥→唯一DSH结构保持，新增接口在API清单及Atlas逐项登记。", "diagrams": []} -->
<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "私有协作回调复用DataHub控制密钥及原scope；public-data仅导出既有有界JSON读取器。数据来源、Broker、SDK取消、研究仓和原件冻结拓扑不变。", "diagrams": []} -->
<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "service.send新增显式specialist分支，模型调度仍由DSH执行；Automation保留原独立准入和日程，不自动开启协作或追加模型调用。", "diagrams": []} -->
<!-- architecture-review {"group": "files", "structure": "unchanged", "reason": "专项质量门在原quality_result之后保留否决；新增账本位于账号私有根而非outputs，报告正文、导出版本和规范文件仍归原交付链。", "diagrams": []} -->
<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "既有研究preset增加受控插件，继续使用原生continuable子会话和settlement；不改固定DSH、不创建进程或第二loop，原Native/Docker双进程边界保持。", "diagrams": []} -->
<!-- architecture-review {"group": "capabilities", "structure": "unchanged", "reason": "四个协作工具在原目录投影，不直接可选；角色冻结现有Skill版本及资源摘要，原能力发布、数据授权和原生审批保持。", "diagrams": []} -->
<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "既有Checks追加三项离线模块，Mac安装同一步追加导入及资源核验；不增runner/job/依赖/时限，Router完整L4及原三门不变。", "diagrams": []} -->
<!-- architecture-review {"group": "private-multiuser", "structure": "unchanged", "reason": "固定specialist-control回调加入已有租户callback名单，沿账号独立Host/Store/DSH与私有密钥；普通用户不能伪造原生终态，网关和账号根隔离拓扑保持。", "diagrams": []} -->


## 合并前独立评审与现场审计更新

独立评审发现并修复两项P1：保留原research_report_delivery=bound接受门，以及解析原生reasoning+可见JSON文本。API8项与运行时19项定点通过；评审复核未发现新明确P1/P2。补齐角色源码文档映射、四项API清单、API Atlas、README复核和Python索引；项目约束检查通过。

Router选中其余本地回归536通过/1原有跳过。现场常驻仍为b800e503，active=null，拒绝切换；doctor还报告旧现场环境及端口归属不明，不能从健康HTTP推断可部署。Docker原先未运行，已启动现有Docker应用但尚未完成产品验收。真实小样本按官方Flash高峰价估算三次约$0.36，本轮$1总上限请求已提出，尚未获得费用确认，未调用模型。

## 2026-10-30 原 PR 刷新记录

已核对本聊天原任务、原 common、原 feature 与 integration 身份。原账本仍为
`specialist-collaboration-20261028`，修补计数为 0；原 PR #246 未关闭或重建。
从 GitHub 正常获取主线 `cf7ffa267cf68de0d56e37af60a05d057fb37753`，在原 integration
保留旧候选 `d8e36d8545ddcbc56f87a4e8c5b869d7203eaf4b` 为第一父提交，创建合并源提交
`53cecb924e4ee22e2f31db412eaccaa2e93141b7`。15 项冲突限于文档、生成物和原 Mac
安装 workflow；双方新增合同、维护检查与 API 均保留，没有业务源码冲突。

原 Mac workflow 只下载 specialist-panel.mjs，未把它纳入后续字节摘要清单；本次补齐
同一步实际字节比较，同时保留主线的 watchlist-import、维护作业身份和原全部检查。
API 清单合并为 415 声明／412 唯一接口，生成物固定到上述已存在的合并源提交。
没有新增 job、runner、依赖或时限。

用户后续已批准真实模型验收总额 $1；早期“待批准”段落保留历史时间归属。当前刷新
尚未发起真实模型请求，不追加额度，不自动重放已受理或接受未知的请求。刷新后的
完整 Router、本地验证、独立评审及同候选原三 CI 仍待执行，旧绿色结果不认证新候选。
源码合并与隔离 Native／Docker、真实模型及常驻部署分别留证；完整 apply/resume、
私有 launchd、旧实例首次准入／退役和 Wind 当前清理未验收前不得切换。历史 Wind
无归属记录保留 UNKNOWN。当前任务不是生产验收完成或 cleaned。

### 刷新候选独评修复

对 `822b34f9` 的 Python／JS 独评各发现一个 P2，均已在原 feature 分支修复，尚待
最终候选重新独评：普通回合取消会误取消历史协作；合法多版计划可能超过适配器的
1 MiB 回执限制。前者按当前 Host 回执 `specialist_run_id` 绑定校验、对账、取消及
质量投影；仍绑定的协作不因 UI 切换模式而解门。后者只对固定协作端点使用 4 MiB
读取，并在写入前同时检查持久账本及回执投影；普通 DataHub 默认限制保持 1 MiB。
超限拒绝，不截断、不删除历史、不自动重发。

实际 RED：普通取消回归 1 fail／1 pass；大回执 bridge 1 fail。修复后专项 Python
83 pass，运行在既有系统网络沙箱下且显式禁用 Framework collectors；固定 DSH
`7ecf564f2e09b829240c5553687223bdd1e2df73` 安装闭包经原验证器核对 16098 文件，
摘要 `5ad78f676fbff7455085d1695bdd7816f552298a00fe1bfb886d41448916045a`。
指定该固定闭包及原任务解释器后，相邻 Node 专项 81 pass／0 skip；最初未指定它们的
56 pass／2 skip 保留原记录，不替换为“原轮通过”。完整 16 节点、每节点约32 KiB、
三版计划也在真实临时 Store／SpecialistLedger 中通过，回执超过1 MiB且低于4 MiB。

独评期间一次未加载完整隔离 fixture 的临时 API probe 意外调度了 Framework
collector，随后正常关闭；未保留完整 PID／临时根及系统网络见证，外部副作用为
UNKNOWN。该轮不能用作无外部请求或现场验收证明。后续正式 Python 回归加载原
fixture、显式关闭 collector 并使用既有系统网络沙箱；不重放该裸 probe，不读取
生产账号或业务数据以补证。原审查日志保留在原 integration 的 `logs/pr246-refresh/`。
