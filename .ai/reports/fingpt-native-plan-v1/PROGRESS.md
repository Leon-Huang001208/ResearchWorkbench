# PROGRESS
1. 宿主 macOS；功能开发；范围原生 Todo + 当前研究计划投影，交付与 Todo 独立。
2. worktree `/Users/leon/.codex/worktrees/fingpt-native-plan-v1/ResearchWorkbench`；基线远端 master `f8adae050900e2209bf3f10025b901dea692cdee`，只读 ls-remote + fetch exit0；主工作区保留。
3. 顺序：固定源码/装配核对 → RED → 投影/guard/UI → GREEN/原生集成 → 文档/plan/交接。
4. 当前 pin `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0` 已随上游更新；禁止回退或升级；重新核对契约。
5. Harness runtime --verify valid=true；新会话 `fingpt-native-plan-v1-20261009` 启动 exit0。
6. 复用已批准环境 `/private/tmp/rwb-claw-test-env.Z0DP8D`，批准证据基线 claw-recovery-20261009-PROGRESS.md:12,27；不安装依赖。
7. 基线 JS 四个 catalog：67 pass/0 fail/0 skipped/0 todo，exit0；logs/js-baseline.log。
8. 风险：历史不全/坏日志不能标绿；turn 清空，无稳定 item ID；权限与48工具/4子任务预算不变。
9. 禁止付费模型、发布、生产重启；CI/安装/模型 live 独立 NOT_RUN，缺证据不完成。

## 待完成
任务0、1、2、3完成本地实现及证据；任务4本地闭包通过，外部验收按BLOCKED.md逐项交接。
总体验收BLOCKED，不标已上线或跨平台已验证；固定此目录恢复，不重跑已有通过且未变化的证据。

## 证据（逐项追加）
- Python 基线 protocol + event_recovery + runtime_launch：160 passed，exit0（26.69秒）；已有获批环境可运行。
- 当前固定源码 `/private/tmp/dsh-fork-sync-local-20261006`：HEAD与当前pin一致，status干净，已有lib及受管node_modules；Todo inject=['tools','sessionProjections']、必填Config、原生shape和turn清空核对完成。
- RED：protocol 11 failed/23 passed，exit1，logs/python-red.log；JS新增2项失败（精确允许/renderer不存在），exit1，logs/js-red.log。未删弱化已有断言。
- GREEN第一轮：protocol 34 passed exit0，logs/python-green-1.log；JS四catalog69 pass/0 fail/0 skipped/0 todo exit0，logs/js-green-1.log。
- 原生无模型集成：首次探针的YAML提取正则过早结束（exit1，logs/native-integration-1.log），修正探针后exit0（logs/native-integration-2.log）。真实Loader读取preset Todo段、真实tools/sessionProjections/AgentLoop/JSONL、真实guard、todo_write两次执行和落日志/耐久读、下一turn清空。integration-state/receipt.json。in-process，无监听端口，无生产进程重启，无模型调用；不等于完整HTTP runtime或模型live。

- 新增坏记录RED：4 failed exit1（logs/corrupt-record-red.log），过滤坏记录、错误可见后GREEN。缺口后所属回合可能变化，原断言曾错误允许沿旧回合绑定；收紧为不猜测，并新增完整新回合恢复断言，RED 1 failed exit1（logs/missing-turn-red.log）→GREEN，不放宽断言。
- 装配用例首次未启用research_tools导致RED exit1；明确开启研究preset后1 passed/133 deselected（非skip），exit0，logs/assembly-green.log；完整catalog在最终聚焦测试中全量执行。
- 最终聚焦Python命令：`/private/tmp/rwb-claw-test-env.Z0DP8D/bin/python -m pytest tests/research_web/test_protocol.py tests/research_web/test_event_recovery.py tests/research_web/test_runtime_launch.py --confcutdir=tests/research_web -q`，178 passed、0 skipped，exit0（41.86秒），logs/python-final-2.log。
- 最终JS命令：Node24 `--test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_workbench.test.mjs tests/javascript/research_web_report_workflow_v0.test.mjs tests/javascript/research_web_guard.test.mjs`，69 passed/0 failed/0 skipped/0 todo、exit0，logs/js-contracts-node24.log。较最新基线67项增加2项，原57项不退。
- Node24固定插件集成 exit0（logs/native-integration-node24.log、integration-state-node24/receipt.json）；真实落盘事件最终Python投影恢复同一计划版本1:2 exit0（logs/native-projection-final.log）。
- 用户明确扩展文档/生成物白名单；原Project Constraints 11条、Python索引过期均保留失败日志。补齐模块文档/README复核、结构决定、Python索引与API阅读索引后修复，未改策略。
- 完整changed set最终validation plan为L4；`node .ai/reports/fingpt-native-plan-v1/final-validation.mjs`执行9个本地gate全部exit0，验证耗时与证据见validation-results.json。Project Constraints通过、文档治理596文件无违反、Python索引通过、架构82通过、UI72通过、L4 JS110通过，JS全部skip/todo=0。
- 服务管理/本机集成额外catalog共444 passed/1既有Windows skip；对应原生Windows检查明确NOT_RUN，不新增skip、不删除平台测试。
- ruff exit0；black4文件exit0；isort exit0；聚焦mypy exit0。完整mypy导入闭包exit1/14白名单外错误，logs/mypy-import-closure-final.log，不把聚焦成功替代完整结果。
- `node --check app/research_web/ui/app.mjs`及`git diff --check` exit0。边界回执验证8个源pin/依赖/安装/CI/策略/service文件与HEAD字节一致，受管manifest14文件哈希一致；主工作区原14项未跟踪内容保留。最新远端master结束时仍f8adae05。
- worktree已绑定短期分支`codex/fingpt-native-plan-v1-20261009`，基线HEAD未变；未提交/发布，候选字节不可借master CI认证。

## 下一步
不重复本地检查；仅在用户授权或环境变化后继续对应外部门，必要时重新核实master/候选并绑定新的CI与安装证据。严格类型闭包修复须另行裁决白名单。

## 最终补充（覆盖前述中间数量）
- 坏记录断言加上“之前存在completed清单”的负对照及缺失type/布尔seq；缺失type RED 1 failed/5 passed exit1（logs/malformed-envelope-red.log），修正后最终聚焦Python **180 passed/0 skipped，exit0，39.26秒**（logs/python-final-3.log）。先前178是中间结果。
- 最终9个L0→L4本地gate重核全部PASS，完整Git changed set **44路径**与plan相等；复核脚本不省略未知风险，plan仍L4。logs/final-gates.log与validation-results.json保存实测时延，最终总59秒向上取整。
- 回执构造最初错误宣告非失败状态需要升级、继而未使用必需外门风险ID；两次validator exit1保留日志；修正receipt和生成器后validator exit0/valid=true/result=BLOCKED、9本地/4外部门，mergeReady=false/releaseReady=false。没有修改验收算法或策略。
- Harness最终记录status=blocked、外部授权类别、已执行本地verifier passed、59秒；Harness enforce exit1“latest outcome is not completed/passed”为真实未完成硬门，不伪造完成记录。外部项没有执行。

## 第一次自动续跑：独立浏览器视觉证据
- 上轮分类为实质进展；先读本PROGRESS/BLOCKED。只读审计exit0：原44路径与plan相等、8个pin/依赖/安装/策略/service边界哈希相同、9本地PASS/4外部门NOT_RUN；产品diff SHA256 `0ac19587e73cdb0a36d62010c1f5088920fe5d1d03c59fd06b76fa3db41b65df`。未重跑已有测试。
- 有可继续的本地独立项：用真实固定插件日志构造只读浏览器预览，未启动产品服务/模型。browser-use插件bootstrap一次失败，macOS原生classic-level模块签名无效；不安装依赖、不改系统签名，改用已启用CUA浏览器控制成功。
- 预览源码仅位于报告目录，GET资源精确allowlist，不暴露checkout或秘密。`/private/tmp/rwb-claw-test-env.Z0DP8D/bin/python .ai/reports/fingpt-native-plan-v1/browser-preview-server.py`，专属进程PID33032/回环端口52497/exec session64317；fixtures由真实JSONL与project生成，负向协议样例分别标注。
- 浏览器六项PASS：真实计划两项in_progress、全量替换完成清单、刷新同一版本1:2、真实耐久日志下一turn无计划、坏数据错误可见且不保留完成清单、长文本与HTML转义（img=0、overflow=false）。截图browser-completed.png、browser-next-turn.png、browser-bad-event.png、browser-long.png；browser-receipt.json。没有通过页面调用研究API或付费模型。
- 截图观察确认窄面板文字自然换行、不渲染img标签；初次reload后的AX索引变化导致选中长文本样例，读取新状态后按唯一语义按钮完成所有场景，未盲重试旧索引。
- 标签页已关闭；对本任务已认证exec session64317发SIGINT，exit0，browser-server.json状态stopped。未触碰生产runtime。
- 此证据只证明真实浏览器渲染原生日志投影，不替代完整产品研究live、模型live、干净安装或同平台CI。当前仍保留原外部授权阻塞，Goal不标完成。

## 远端发布授权与准备
- 用户明确允许提交、push、创建PR及自动通用/macOS CI；不包含merge/auto-merge、Windows/Linux dispatch、依赖安装、付费模型。授权取代本任务原默认不push边界，不扩大其他权限。
- 读取docs/actions-budget.md；实时GitHub API为PUBLIC；当前标准macos-14成功作业可启动，最近五次成功实际602/386/588/412/728秒，均值543.2秒，保守权重约99.6分钟/次（非public标准runner收费量）。证据actions-budget.json。Git fetch/ls-remote确认远端master仍f8adae05，exit0。
- 使用iteration-delivery的基线/隔离/验证原则；其控制器start只创建新功能worktree，没有采用当前worktree的入口；publish会默认尝试主线推送并调用auto-merge，不能在本次明确“不含merge”授权下调用。保留当前已验证codex工作树，按GitHub分支push+PR流程发布真实候选，不伪造控制器receipt，不执行主线发布/cleanup。
- 发布原始工具日志仅保留本地；提交可审阅源码、文档、必要结构/计划/集成/浏览器摘要和合成数据证据，未发现模式扫描命中的密钥/私钥。PR说明已写pr-body.md，待提交/push/PR与自动CI证据绑定。

## 已发布候选与实际CI
- 发布前候选55路径；一次错误地只传六个源文件给Project Constraints导致exit1，随后完整55路径重跑exit0/0违反（logs/precommit-constraints.log）。不是产品失败、不修改策略或断言。
- `git commit -m "feat(web): restore and display native research Todo plans"` exit0；候选`c10cb6bf58fa36889d5647bc6eb99e53ccf27340`，父提交f8adae05。提交后app/docs/outputs/tests二进制diff SHA仍0ac19587…，已测产品字节没有变化。
- `git push -u origin codex/fingpt-native-plan-v1-20261009` exit0；`gh pr create --repo Leon-Huang001208/ResearchWorkbench --base master --head codex/fingpt-native-plan-v1-20261009 --title ... --body-file .ai/reports/fingpt-native-plan-v1/pr-body.md` exit0，PR https://github.com/Leon-Huang001208/ResearchWorkbench/pull/90 已attach当前聊天。
- live GitHub PR：OPEN、head=c10cb6bf、base=f8adae05、autoMergeRequest=null；merge_preview=778959523ee5be7401bab01253e43f5ce79f198a（不是已合并）。未主线push、未merge、未auto-merge。
- 当前真实自动run：Project Constraints 37888849149已success；Research Web Checks 37888849128和Mac Bootstrap 37888849125在运行。run的headSha均c10cb6bf。未dispatch/rerun其他平台。
- publication.json记录来源、源候选与本地后续报告的分离；后续证据暂不push，避免报告提交触发重复Mac CI，不能拿未发布的本地报告字节当CI候选源码。

## CI等待期间的作用域补查
- 核对固定DSH的dsh-base包确实依赖tool-todo与session-projection；补查原生agent-preset registry的作用域装配，而不将已通过的宿主级真实Loader/工具执行等同完整preset。
- 新增报告专属探针native-preset-integration.mjs；前三次exit1均未改产品源码：两次CLI直接锚点缺少group模块，读取真实依赖声明后确定group由app-boot锚点提供、preset-registry由agent-preset锚点提供；第三次进入实际registry后，探针setup回调错误返回mount结果，触发TypeError(commit不是函数)。与固定源码测试harness的void setup签名对照，根因明确。
- 连败3次后停止直接重试，先完成独立Mac CI/Doctor/checkout取证。Mac Bootstrap37888849125已success，doctor schema2/installation_ok=true/product_ready=true，runtime/web均ready=true；服务已按workflow正常stop。checkout日志为真实merge预览7789595，父提交本地Git对象核对为f8adae05+c10cb6bf。没有rerun或dispatch。

## 集成证据纠正（原始工具执行真实；旧最后回合收据失效）
- 依据原生fixture签名修正setup的void返回后，作用域探针进入耐久读取，原生校验器拒绝`turn/start`：手工下一回合前缺少`turn/end`。这是报告专属测试夹具错误，不是产品代码或DSH版本缺陷。
- 对原integration-state与integration-state-node24完整日志实际执行原生SDK open/read，均明确SessionPersistenceCorruptionError；此前只读有效前三条前缀、随后未重读最终日志，不能据此认证下一回合耐久恢复。日志与原收据保留；两个旧receipt现标FAIL/earlierObservedStatus=PASS及替代证据路径，日志/native-old-log-read-validation.log记录实际拒绝。
- 原native-integration.mjs新增合法turn/end→turn/start，以及最后整个日志的SDK重新读取；保留失败root，不改写其原生日志，在独立integration-valid-state取得exit0/PASS/finalDurableLogValidated=true。
- 原生preset作用域探针在preset-integration-valid-state取得exit0/PASS：真实AgentPresetRegistry/Loader挂载生产Todo段、宿主根无Todo、no-plan作用域无Todo、两个真实Agent分别工具执行与耐久日志隔离、只清空当前新回合；模型调用0。dsh-base受管依赖含Todo/sessionProjections，source/lib哈希见该receipt。未mock被测插件/guard/投影。
- Python把上述两会话的SDK完整读取事件实际project：新回合plan=None，另一会话保留原Todo；logs/native-valid-projection.log exit0。browser-fixtures改为合法完整原生日志；实际浏览器重新验证下一回合无旧计划，更新browser-next-turn.png与browser-receipt；进程PID67826/端口59338/session41859按认证句柄停止exit0，不留运行服务。
- 此纠正会更新PR证据候选并触发其自动Mac CI；产品app/docs/outputs/tests字节未改变，先前CI仍属于c10cb6bf，不能将其冒充新候选CI。报告后续文件不靠原来的CI认定。
