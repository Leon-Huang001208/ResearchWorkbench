# Claw 原生关联与异常退出恢复候选

<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"既有 Automation 使用原 Store Run 关联字段、原生 Claw 与报告 Runtime；只提前原子保存并约束恢复/取消事实源，不新增模块、调度器、执行引擎、HTTP 路由或持久 schema，因此模块依赖图不改。","diagrams":[]} -->

本地候选结项验收已完成：2026-10-09 用户授权后仅修复共享账本两处共266字节，Harness硬门已PASS，独立全流复核未发现新增损坏。完整57文件计划的五个本地门复验PASS（架构82、完整Node110、0 skip）；原128项Python回归、四QA与三类受控进程恢复/产物字节验收证据保持有效。总交付回执仍BLOCKED/非merge-ready，CI、干净安装、真实模型与其他平台NOT_RUN。

## Goal 与边界

Goal：创建后及时保存原生关联，异常退出后接回同一任务，不重复研究；报告等待原报告校验与产物。
macOS 功能开发，基线 `4a5e7523d7407525d108757727c64f10783203f4` 与远端 master 已核验一致。
独立分支 `codex/claw-native-recovery-20261009`；前轮 FinGPT 候选和主 checkout 保留。
API/schema、依赖锁、DSH、调度/权限和真实用户运行实例不改，不发布或请求付费模型。

## 证据与当前状态

- 基线：六套 Automation 测试 29 PASS。
- 三类创建路径 RED：监控等待时磁盘原生关联为 None；保存失败、未知提交、报告事实源和身份等回归也先 RED。
- 初版修复六套 49 PASS；独立评审指出初始持久化失败可能取消陈旧引用，新增异目标与同目标陈旧两条 RED，修后服务专项 34 PASS。
- 检查点只复用 Store.save 原子索引；保存失败回滚内存，不继续提交；未知原生 admission 不视为成功。
- 报告首次引用验证 Runtime 事实源、目标/版本和新建身份后才保存；初始保存失败只允许停止被证明本次新建的活动报告，恢复/晚到引用失败不取消既有工作。
- 受控 macOS 独立进程 SIGKILL：旧基线三类 FAIL，新实现三类 PASS，同一 Run/主关联恢复，原生创建/发送计数不增加，实际文件 SHA256 不变。
- 进程探针使用真实 AutomationService/Store，但执行器是受控 loopback backend；真实 DSH/model、Office/Wind、他平台 NOT_RUN。
- pytest/pytest-asyncio 的临时安装已获用户批准，位置 `/private/tmp/rwb-claw-test-env.Z0DP8D`，复用主项目运行包只读，不修改主环境/锁。
- 质量工具临时安装已获用户明确授权：Ruff 0.16.10、Black 26.10.0、isort 9.0.2、mypy 2.4.0；主环境/锁未改。

## 当前实际验收

- 六套 Automation 与两套报告 Workflow 测试：128 PASS，0 skip，1 条既有 Starlette/AnyIO deprecation warning；日志 `/tmp/claw-recovery-final-python.log`。
- 完整相关 Node 套件：110 PASS，0 skip/todo；日志 `/tmp/claw-recovery-node-full.log`。
- 文档治理、Python 生成索引、架构一致性与完整 changed-set Project Constraints：PASS，violations 0。
- 最终只读 Python 审查：Approve；初始陈旧引用误取消问题关闭，恢复/晚到引用保存失败不会取消已有报告。
- 进程回执与 sourceSHA256 绑定：`claw-recovery-20261009-process-receipt.json`；三种真实子进程 SIGKILL/恢复 PASS，后台受控执行器和文件校验均独立于 Web 子进程。
- 项目规划器按完整变更集选择 L4，未知测试路径不减门；两项 CI 未运行，总回执维持 BLOCKED/非 merge-ready。

## 授权后的质量验收

授权后四项质量检查已通过；仅修正格式、导入排序和无效noqa，三文件语义 AST/导入集合不变。mypy 使用现有配置与 follow-imports=skip 只核验 service.py，同工具旧基线也通过，不认证全仓库类型质量。格式化后128测试与三类进程恢复再次通过，原12测试AST保持；只读复核确认未引入语义或范围变化。
选中未运行 CI/干净安装维持 NOT_RUN；不得把本地候选称为正式交付。

## 回执与结项审计

- 已按完整变更集保存正式 plan/receipt，validator 返回 valid=true、result=BLOCKED、mergeReady/releaseReady=false；五个策略本地 gate PASS，两项选中 CI NOT_RUN。质量批准阻塞已解除；总交付缺CI/安装证据，最新风险还包括未通过的共享Harness硬门。
- [计划](claw-recovery-20261009-plan.json)、[回执](claw-recovery-20261009-receipt.json)、evidence/ 目录包含实际 RED/最终测试/进程日志，不包含安装日志或真实秘密。
- 进程回执 sourceSHA256 与当前 service.py 一致；原 12 个测试函数 AST 无改动，新增测试未替代原断言。
- 上述等待状态为授权前历史。收到“授权”后已安装并通过四项质量检查；最终语义复核、复验及本地回执闭环完成。当前目标仅交付本地候选，不发布、不更改用户运行实例，不认证真实DSH/model或其他平台。
- 质量日志及同版本基线位于 evidence/*-quality.log / *-baseline.log；临时工具环境未加入项目依赖或锁文件。安装原始日志保留在 /tmp，不纳入候选以避免无关环境信息。
- Harness 最后硬门实际返回 `invalid harness event stream`，尚未通过。先前 Goal 完成标记过早；已重新恢复同一完整目标，正在只读诊断账本。产品测试结果保持有效，但最终本地结项仍须解决或如实记录此硬门。
- 只读诊断定位共享 events.jsonl 第46283行：一个其他任务事件前有133个NUL字节；本任务的开始、验证通过和结束事件本身合法。已备份原账本并生成等长空格修复预览，46805条记录全部可解析，事件JSON/其他字节不变；尚未应用，等待共享账本范围的单独授权。
- 随后诊断期间又出现第46809行同类损坏，原单点提案已被两处合计266字节的提案取代。最新预览46855条记录可解析；两处都只替换等长前导空白，完整事件与其他字节不变。原字节与预览清单位于 `/private/tmp/rwb-claw-harness-repair-two-MgJA5l/`。损坏写入源尚未证明，未改Hook/runtime；待明确授权后仅修这两处并做完整流/硬门与后续审计，若再次损坏立即停止、不扩大范围。

## 逐项验收审计与产物证据补强

| Goal要求 | 当前实际证据 | 状态 |
| --- | --- | --- |
| 三类生产创建路径及时原子保存原生关联 | test_native_run_reference_is_on_disk_before_monitor_wait的三类RED→GREEN；保存失败回滚测试，不预填native关联 | PASS |
| 异常退出后同一Run/关联恢复，不重建或重发 | 最新process-receipt三类自建macOS进程SIGKILL=-9，恢复ID与创建/发送次数断言；旧基线三类缺关联FAIL | PASS，执行器受控 |
| 崩溃前已有产物内容保留 | 独立backend在SIGKILL前真实写出并登记中间文件；恢复后同一路径read_bytes与SHA一致，六份before/after文件归档 | PASS |
| 字节验收能发现内容丢失 | artifact-loss-red三类在自建临时文件中注入字节破坏，均FAIL：pre-crash artifact bytes changed after recovery | 预期RED |
| 保存、提交或归属未知失败关闭 | 保存失败、idle/created/未知状态、未确认admission、缺ID、报告异目标/版本、陈旧引用取消边界等回归；128测试PASS | PASS；普通共享分支负例以Skill覆盖，报告单独覆盖 |
| 报告校验与产物为权威状态 | report validating期间Automation仍running；只监控原报告，晚到session checkpoint；不取消恢复/晚到的既有工作 | PASS |
| 版本锁、无人值守权限、研究/投递双状态保留 | 原12测试函数AST不变；对应版本/权限/投递失败及仅恢复投递测试通过 | PASS |
| 文档、完整changed set、本地检查和真实未验证项 | 正式plan/receipt按57文件更新，五个本地门复验PASS；CI/安装/真实模型/他平台NOT_RUN | 本地候选PASS，总交付BLOCKED |
| Harness最终结项 | 授权266字节修复、原字节持久备份、全部其他既有字节不变、官方全流严格schema与后续append复核 | PASS，verificationDurationSeconds=187 |

原进程探针只证明恢复后最终产物元数据接回，不能证明崩溃前文件保留；本轮已补齐实际字节证据。新旧过程回执均绑定源码SHA，新增probeSHA绑定探针；旧源码SHA为1251ad890f67f42cd116cb4e2c56a691c9b6514411abe9fe1a101671f3f51f04，当前service.py保持560c877b82d86db505ab8910407de877a43de753b0fc5463d5c641a4db7be913。
独立评审发现受控执行器过早发布session完成的竞态，已修复为最终文件写入后同锁追加产物并发布完成；报告保留session完成/report validating阶段。复验正常三类PASS、字节破坏对照三类预期FAIL、旧基线三类FAIL，评审Approve。产品代码和128项Python测试未改，不重复运行已验证且未受此次探针修改影响的产品回归。

授权前历史结项状态：同一共享Harness修复授权阻塞连续三回合，第三次只读复核仍失败，候选与验收SHA无漂移，Goal登记blocked等待授权。候选与原始证据一直保留，未发布。

## 授权后的Harness闭环

- 用户明确授权两处各133 NUL替换为等长空格；应用前核对恰好原两处损坏、行SHA/offset与dev/inode。只作两次定位写，不截断或重命名共享账本。
- 原字节备份以0600保存在0700私有目录，文件及目录均fsync，最终原始备份持久保存在Git元数据目录；完整其他历史事件不纳入Git-managed候选。
- [修复回执](claw-recovery-20261009-harness-repair.json) 与 evidence/harness-repair.log 记录RED exit1→GREEN exit0。独立比较原6,756,714字节前缀：差异恰好266，仅NUL→space；完整JSON后缀和其他既有字节不变。
- 官方readAllHarnessEvents无任务过滤进行完整schema核验；修复即时47,161条与后续独立47,167条均PASS，后续append合法、未发现新增损坏。Harness原生硬门PASS，原pytest实测187秒记录保留。
- 损坏写入源仍未知；本轮只修复已授权损坏，不宣称恢复NUL覆盖前的未知历史或修复宿主Hook根因。总回执保留此未知风险及CI/安装/真实模型/他平台NOT_RUN。
- 完整57文件计划与适用本地门复验完成，产品代码、探针、原测试及主checkout受跟踪文件未因账本修复改变。本地候选目标达到，正式发布/CI/真实模型/其他平台不认证。
