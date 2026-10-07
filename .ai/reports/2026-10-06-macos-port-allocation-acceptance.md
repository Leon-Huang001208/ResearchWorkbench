# macOS 双运行时端口分配：实际验收进度

状态：IN_PROGRESS。未宣称本地验收完成、合并就绪或整个 goal 完成。
宿主：macOS Apple Silicon；任务类型：功能开发及本机隔离验收；无桌面/Tauri工作。
仅 macOS 本地及同平台 GitHub CI 是当前宿主任务的完成条件；其他平台保留交接/未执行状态，
不作本 Mac 任务前置条件，也不因此宣称已支持。

## 源码与范围

- 实现分支：`codex/macos-runtime-port-allocation-20261006`。
- worktree：`/Users/leon/.codex/worktrees/macos-dual-runtime-acceptance/ResearchWorkbench`。
- 完整分支基线：`05326b6066f96a572db4ac87f3bdc041ff92003f`。
- 最近已提交检查点：`1872bbc2c68250d5bab9b174a19f603ae7e6f962`；已审Doctor投影修复；8e镜像的真实生命周期与1872宿主/Native往返已完成。最新master整合及Mac CI仍未完成。
- 原 Task1–12 分支、提交及证据保留；主 checkout 已由其他执行者推进到平台职责文档提交，未回退。
- Harness 后来已一致；更新执行者未知。未重开调查或改 runtime/global 配置。

完整 `05326b606..e21c7b5f` 计划已包含48条源码、测试、生成文档和报告路径，
不是 Task12 或单轮修复的窄 changed set。现有 v3 planner 选择L4；管理内核11项SHA-256匹配。
`logs/macos-port-allocation-complete-plan-e21c7b5f.json` 保留完整计划。
该完整48路径 Constraints 与 documentation governance 实际通过。
新源码和本报告将纳入后续最终完整计划，旧计划不会伪装成最终HEAD计划。

## 实际 Native 安装与只读诊断

人类明确批准仅测试目录的锁定安装。隔离目录：
`/private/tmp/rwb-macos-ports-live.3av1gO`，checkout 子目录为 detached Git worktree，HOME 为 home 子目录。
使用已安装 Node24.19.0、现有 HTTP代理29758，仅对安装命令设置环境变量。
未安装全局包/系统工具，未改变依赖锁、全局代理、宿主软件源或日常数据/凭据。

公开命令（cwd 为测试 checkout）：

```sh
env HOME=/private/tmp/rwb-macos-ports-live.3av1gO/home \
 RESEARCH_NODE_BINARY=/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
 HTTP_PROXY=http://127.0.0.1:29758 HTTPS_PROXY=http://127.0.0.1:29758 \
 ./setup-web.sh --runtime native --no-start
```

首次调用发生在 worktree 解压尚未结束时，exit127/入口不存在，是控制器顺序错误，不是产品RED。
同一 worktree 创建随后exit0，确认入口后重试。e21c7b5f 真实安装exit0，输出installed/started=false：
独立受管`.venv`按web.lock安装、CJPY0.5.2随包安装、DSH固定c919b2a460753859665db3f60143d525fb9140cf
实际clone并以pnpm11.7.0/frozen锁构建成功。npm瞬时重试和构建警告均保留。

证据：`native-install-e21c7b5f.log`（127），`native-install-e21c7b5f-retry.log`（0），
测试 checkout `logs/setup-web.log`。均位于上述测试目录，未修改旧证据。
公开`rwb web status --json`与`doctor --json`各exit0：schema2，两项服务running=false/ready=false，
installation_ok=true、product_ready=false，与no-start一致；不是生命周期健康PASS。
更新测试checkout到efd1d37e8后，同公开安装器刷新exit0，复用已验证固定DSH构建；
证据`native-refresh-efd1d37e8.log`。尚未以该源码进行实际start。

### 正常 Native auto-start 实机阶段（b9ff60fa）

R4失败恢复补丁24bb6df8、R5公开安装入口b9ff60fa均获独立限定patch批准；不等同整goal批准。
新0700 HOME=`/private/tmp/rwb-macos-ports-live.3av1gO/home-live`，保留原HOME及canonical根。
以正常公开`./setup-web.sh --runtime native`（没有no-start，也没有手工build-lock/根清理）
执行真实受管venv重执行、锁定安装与固定DSH完整构建。env-i只保留标准系统PATH、该HOME、
已验证Node24.19.0、仅命令级现有HTTP(S)代理和任务私有RESEARCH_CREDENTIAL_HOME。
无全局包/系统工具或真实凭据/Keychain。源精确b9ff60fac1c94f8ff44ad4710f5070c5e77307ed，
首次venv已受管、依赖与固定输入允许复用；HOME中的DSH source及构建实际重新完成。

安装exit0/installed/started=true；Web53170、DSH53171，不占日常8088/3081。
公开status和Doctor各exit0：两角色owned/running/ready，installation_ok/product_ready均true。
首页及/static/app.mjs实际HTTP200。公开restart exit0：Web保持53170，DSH重新选择53783，
两角色仍owned/ready；不假称所有端口必须保持同值。公开stop exit0，listener_pids现有检查
确认53170/53783均closed；8088仍PID69730、3081仍PID68985，未停止/改变日常实例。
再次公开start exit0：53170/53783，owned/ready。重启及停启后控制token/其他字段/实际Web origin
比较均true；基线仅留测试进程RAM(session92740)，无磁盘token快照或原值输出。

实际日志/回执（均在该task目录，不改旧记录）：native-live-install-b9ff60fac.log、
native-live-{status,doctor}-b9ff60fac.json、native-{root,app}-b9ff60fac.{html,mjs}、
native-restart-b9ff60fac.log、native-restarted-doctor-b9ff60fac.json、native-stop-b9ff60fac.log、
native-start-again-b9ff60fac.log。文件扩展名按对应实物而非将brace拼写误当单一文件。

功能持久化尚未PASS：无秘密空会话创建两次均HTTP503/agent-preset/invalid，保存了两条failed
session元数据；这些failed IDs/title/status在restart/stop/start后确实相同，但不算成功研究会话。
现有DSHClient认证后list presets实际成功、含research-web；一次直接同请求错误诊断（既有failed ID）
取得脱敏reason：research-tools loader不能在缺inject声明时访问spawnProcess。失败发生在
session.selectModel之前，不归咎于缺模型key，不填假key/手改preset绕过。
诊断第一次误拼DshClient而非DSHClient的ImportError为控制器错误，不是产品RED。

### 成功会话与样例数据（efff4651a）

Cordis getter 最小修复 efff4651a 已经独立 TypeScript 审查批准。先正常停止测试 Native，
更新测试 checkout，再正常公开安装器 no-start 刷新和 start，各 exit0；53170/53783 owned/ready。
正式 API 创建无秘密研究会话返回201/idle：106746f3-4612-4192-a69f-b49b6bea2743，
title=macOS verified runtime fixture。未配置假模型 key、未发送模型生成请求。
正式附件 API 上传39字节 runtime-fixture.csv 成功，附件075d5a82d5196171ba5590fd；
样例 SHA-256=47ad7335dab05dd4668880628ab1fdbee1f1fd9642a4cd160484f167353912eb。
证据 native-session-create-efff4651a.json、native-fixture-upload-efff4651a.json、
native-logs-efff4651a.txt。成功会话的 Docker 往返和回到 Native 后下载校验尚未执行。
构建前 Native 已通过公开 stop 停止，日志 native-stop-before-docker-efff4651a.log；日常实例未停止。

## Docker网络事实与限制

固定Node24.19.0/Python3.12.13基础镜像真实拉取成功，不能再笼统写成镜像网络不可用。
immutable05326b606基线的三次构建均失败：首次在Dockerfile frontend OAuth、未到APT；
命令级现有HTTP代理使frontend成功，随后APT gcc下载失败；标准RUN代理参数的第三次
仍在APT以连接关闭/503、exit100终止。无最终镜像，Docker生命周期未执行。

日志：`/private/tmp/rwb-macos-ports-build.S7DCdf/build.log`、`build-http-proxy.log`、`build-run-proxy.log`。
一次有限Range下载不能证明完整包可用。后续无挂载/无发布端口的固定Python容器实测同一官方GCC包：
HTTPS返回200/16300644字节，HTTP返回200/3802050字节；这是传输差异证据，非包名/版本错误证明，
也不证明根因已完全确定。未关TLS/签名，未改全局源或Docker配置。官方源HTTPS构建复测未执行；
同一原因无新处置依据时，不重复完整构建。

随后进行一次针对HTTP流水线兼容性的有界下载诊断：原固定Python镜像、无挂载/发布端口、
180秒上限，只更新原官方APT索引并download上述精确gcc版本，不install软件；
`Acquire::http::Pipeline-Depth=0`、Retries=0、HTTP Timeout=20。
签名索引读取完成，但包传输仍返回Remote end closed connection，容器exit100。
证据`/private/tmp/rwb-macos-ports-live.3av1gO/apt-pipeline-off.log`。
关闭流水线未解决这个HTTP路径问题；不再重复HTTP下载/构建。未改变源、TLS或签名校验。

基于HTTP转发失败与HTTPS CONNECT完整下载的差异，换用既有SOCKS转发进行一次同包下载诊断：
仍原官方源，Acquire::http/https::Proxy=socks5h://host.docker.internal:29757，Retries=0，
Timeout20/整体180秒。signed索引9285kB及GCC16300644字节完整下载，容器exit0。
证据apt-socks-route.log。此输入不同的有界诊断不是重复旧HTTP配置；未安装软件或改任何源。
证明这条下载路线可用，不证明完整镜像或生命周期。HTTPS换源当前已无必要，尚未执行。

宿主Registry OAuth直连只读curl（响应丢弃、不输出token）仍exit28/http000/连接超时。
独立源码核对确认Docker专属_environment使用minimal_environment且直接Popen(env=env)，
过滤HTTP_PROXY/HTTPS_PROXY/NO_PROXY；task HOME Docker配置并非宿主CLI OAuth代理入口。
Docker 专属安全代理修复 c19ff833 已经独立 Python 审查批准；共享 minimal_environment 未扩大。
task HOME 唯一无秘密 Docker config 指定既有 SOCKS HTTP build proxy 与 HTTP CONNECT HTTPS
build proxy；宿主客户端仅命令级127.0.0.1:29758。未换工具路径、全局代理/daemon或认证配置。

精确 efff4651a 的公开 Docker no-start 安装实际越过 APT，但 fs-ext 的 node-gyp 下载头文件
因 Undici 不接受 SOCKS HTTP_PROXY 而失败。日志 docker-install-efff4651a.log，
build history bdfcljfcrrhgjtk5yepbod94u。不是包名或 APT 新失败。
Docker builder 同源本地 Node headers 修复40375ee80经独立 TypeScript 审查批准；固定 Node
镜像实际核对二进制和 headers 均24.19.0，最终 runtime 不继承 headers/nodedir。
一次新源码公开构建实际完成 fs-ext CXX/link/COPY/gyp info ok，进入 tsdown；随后通用64KiB
输出预算触发 runtime_output_limit，controller 终止本次构建。不是头文件下载失败复现。
证据 docker-install-40375ee80.log、docker-build-history-40375ee80.log（66884字节），
history y0kj6tq7ox5eg3wvg7mweufua。无最终镜像，Docker 生命周期仍未通过。
当前限定修复仅固定 Compose build 的每流2MiB有界预算并复用脱敏stream；普通命令保留64KiB，
超限仍失败并清理本次进程树。未加 quiet、截断伪装成功或省略错误。

9d0e7909d 已经独立规格/Python审查批准：真实RED4，初次闭包1FAIL/373PASS（构建判定过早
读取安装身份，导致首次预检回归）；短路修复后相同闭包374PASS，原失败保留。JS104及所有
该修复文档/完整性门通过。精确源的公开 Docker 安装仅重新执行一次，日志docker-install-9d0e7909d.log，
exit0/installed/started=false；接受镜像sha256:0cea41a3b81899dbbb0f13f3daa01c585675327c00b2615d686bd320c216078b，
完整脱敏构建日志382673字节。仅认证完整镜像/安装，非生命周期。

公开 runtime use docker exit0，首次公开 start exit1/docker_start_failed。Doctor：Engine/Compose/
image/data ready，container absent；public logs exit0空输出。限定安装标签的Docker events
证明本次f1e70779...容器create/start/die/destroy。已有挂载持久日志明确container_startup_failure，
launcher_modules/RuntimeError；没有DSH/Web ready。控制token/其他字段/Native53170 origin的RAM
比较仍true，未清理真实数据或无关服务。证据docker-start-9d0e7909d.log、
docker-doctor-failed-start-9d0e7909d.json、docker-start-events-9d0e7909d.log及既有Docker runtime日志。
一次只读、无网络、无凭据挂载的guest检查285个profile links，只有typescript失效（仍指Native绝对路径）。
第二次无挂载只读image检查root node_modules/typescript不存在，但.pnpm包6.0.3已存在。
证据docker-modules-readonly-audit-9d0e7909d.json、docker-typescript-readonly-audit-9d0e7909d.json。
独立只读诊断确认stager的canonical图已选该optional peer资产，但遗漏上游虚拟alias锚点
需要的root别名；不是缺新依赖。最小staging别名修复正在RED→GREEN，不删profile链接、
不清缓存、不弱化broken/outside-source检查，不重复start或同源build。

随后独立推进当前Native：初次切回命令遗漏已验证Node路径，前置检查拒绝（exit1/unsupported），
这是控制器命令环境错误。公开no-start刷新exit0，补齐同已验证Node24路径后的公开use native
--stop-current/start/status/Doctor均exit0，53170/53783 owned/ready；tokens/extra/origin仍true。
GET原成功会话200，ID/title/idle保留；附件200/39bytes/SHA完全相同。native-persistence-9d0e7909d.json
保留具体布尔与摘要；不是Docker成功往返。最后公开stop exit0，测试监听关闭，日常68985/3081
及69730/8088未变。Native刷新与mode-use第一条未等终态即启动下一条属于控制器顺序瑕疵，
实际终态和失败保留；随后切回/启动严格串行，不将该并发调用作为顺序生命周期证据。

99c4365ad 的最小修复只扩展现有staging alias循环，保留原有production visited与私有边界，
不纳入未选开发依赖、不改固定DSH、不删除共享缓存。真实Node虚拟锚点普通/scoped peer RED2，
staged58、相邻Python199、JS91和Docker13 GREEN。初次Constraints因缺必需模块文档FAIL保留，
补齐后完整八路径PASS。独立规格/Python patch审查Approve，完整特性分支审查明确复用未变部分、
补审9d..99及manifest交互后Approve；不当物理PASS。证据任务报告
.ai/reports/2026-10-07-docker-root-module-alias.md与/private/tmp/rwb-root-alias-checks.MC930G/。
测试Native已stop/端口closed、测试checkout clean后switch精确99；公开Dockerno-start安装
仅执行一次，日志docker-install-99c4365ad.log，当前进行中。

上述99实际构建/安装随后exit0，接受image e19536ca2bb6c461f7a4804acefaeb1b82dbd382d844cadee2f4a6c5b8fd6bb8。
实际公开start再次exit1，但已越过launcher_modules；DSH退出1/runtime_wait，既有共享data_root/logs
显示yaml@2.9.0/dist/compose/composer.js缺../doc/directives.js。独立源码核对确认误按doc目录名
排除了已发布dist/doc运行代码，而不是TypeScript修复无效或缺新依赖。
655ab87d0以同一规则修正遍历剪枝和最终过滤，仅明确发布目录内嵌套doc/docs例外；顶层文档、
硬开发目录、README/suffix和source/alias/manifest安全规则保留。RED4、最终staged71、相邻211、
JS91+Docker13通过；不将后加测试倒计为212。独立规格/Python审查Approve。

精确655正常公开Docker安装仅执行一次，exit0，接受image
fb79ce31ef512e98fcab4e9c698be48719c29660661ef832ce83cb5feac91c4e。公开start exit1：
新日志未再缺TypeScript/YAML模块，runtime子进程仍alive(returncode null)，Supervisor报
RuntimeStateError/runtime_probe后清理。Doctor absent，控制token/extra/Native53170 origin RAM均true。
不把新构建或越过旧缺口当作生命周期PASS。docker-install/start/doctor-failed-start-655ab87d0
对应文件与已存在research-web/logs保留实际失败。

有界诊断：实际state以只读mount和匹配Compose的RW mount分别只读stat/strictguard检查，均accepted；
/state显示root0/privateleaf10001、700。正常源文件入口的无server ContainerHealth构造成功/探测false；
最初-I直接import docker namespace失败是控制器入口错误，保留后正常文件加载修正，不算productRED。
另建独立probe-auth-case.pJYoxy，用原private-leaf初始化和原auth writer写合成诊断cookie，不触碰实际
auth或credentials；fresh及existing-leaf/remount outerguard均通过，FD/path身份稳定。该fixture父目录
显示10001，未覆盖实际父目录0前态；不能据此证明或否定live期间映射，也不能认证真实认证。
所有诊断只记录元数据/阶段/布尔，未输出控制值。owner映射假说未证实，不继续重复655启动或构建。
下一最小动作限定原guard拒绝分支增加stable reason/phase/changed字段名私有日志，不记录路径、
UID值或token，不改条件、异常文本、权限、公开五字段schema或引入探针框架；独立实现/审查后
才有依据执行一次新源码取证。当前实际拒绝位置和原因仍UNKNOWN。

0b7c801cf 的拒绝点日志补丁（无行为/异常文本/权限/公开schema变化）独立审查Approve。
本轮日志-only闭包304 Python、最终launch96、JS91；随后主会话共享guard消费方
ServiceManager/Setup/Mode/Docker/API补验729PASS/1 DeprecationWarning/231.93s。
精确0b7公开构建exit0，接受f3f6f17d69e7fac72e7500dd38327c748c6b4750b9be6d4221cb53d43d8eca9e；
一次公开start仍exit1。新增日志首次明确：identity_changed/post_yield/ancestor/changed=uid,gid，
dev/inode/mode未改变。它证明祖先所有权变化导致拒绝，不证明具体位置或方向，也不认证mapping安全。
2a137b424 第二轮仅增加root_pair_to_runtime_pair/reverse/other及leaf/parent/other_ancestor分类，
混合/foreign/重合身份为other，原拒绝条件不变。RED30、launch131、真实本轮340 Python、JS91及
完整九路径门通过，旧计数不改写；独立审查Approve。当前新源码仅进行一次正常公开构建，
docker-install-2a137b424.log；没有实施初始化豁免、chmod/chown、预写实际auth或重复旧source启动。

## 只读交付预检与整合边界

现行main actions-budget已读；GitHub API当前PUBLIC，默认master。最近5个成功macos-14标准Job
分别506/555/538/311/407秒，平均463.4秒（约7.72分钟、内部权重约84.96），均非self-hosted。
这是当前public-standard可运行条件，不是本分支CI通过。logs/macos-remote-preflight-*保留API事实。
远端master已到ddcdd9784d8eda2918b8987ca8b679375e67291d；相对053特性基线新增34提交/69路径，
22条与当前改动重叠。当地Git对象存在；仅做三方merge-tree只读预览，没有merge/reset/覆盖。
认证、Supervisor、模块文档等存在冲突，必须独立本地整合验证后才能出版，当前不具备远端阶段条件。
上游新增auth-bootstrap/auth-output私有handoff及PID/authority/cwd绑定；它未改runtime_state/healthcheck，
不能仅凭机制更新认定已修复本次guard失败。后续需完整保留认证单元及当前端点/origin/lease/清理保护，
不把models/capability等额外行为当本次故障修复。无push/PR/merge/tag/dispatch/rerun/发布或cleanup。

## 原目标完整验收闭包

Docker 入口宿主 Python3.12：重新核对原 objective 未发现“宿主无需 Python”的明确要求；
已批准原实现计划明确 stdlib-only host bootstrap/统一 rwb CLI，并指定宿主Python3.12。
现有实现与安装文档一致，未顺带移除此依赖，也未把 Docker 描述成只安装 Docker Desktop 即可。

原 goal 基线4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7到99c4365ad的完整计划含206路径
（含三个主任务收尾产物路径），L4；已生成主计划.ai/reports/2026-10-06-macos-port-allocation-plan.json。
特性基线05326b606到99另有61条tracked路径+同三个主收尾路径的64路径计划
logs/macos-port-allocation-complete-plan-99c4365ad.json；不混用这两种范围或仅用Task12子集。
原goal完整206路径Constraints实际exit0（工具墙钟0.054385917s），旧205路径记录保留。
本轮实际 L0 文档治理/索引、L1验证合同99项JS与架构/跨平台合同66项JS、L1 Python853 PASS/1原有skip、
全204路径 Constraints、L2 Python195 PASS、Docker JS13 PASS、L3协议19 PASS及L4 JS91 PASS。
各门独立日志位于实现 worktree logs/macos-goal-final-*；Python保留5项警告。
这些是记录提交范围的实际运行，不改成未来HEAD重新运行；9d补丁另补验受影响合同及JS闭包，
原goal全205路径Constraints也实际通过。最终回执将逐门明确来源/覆盖关系。
计时核对：局部 logs/docker-build-budget-receipt.json 的 Constraints/独立文档治理/索引
复制了JS复合命令2.21s，不能视作这些门实测耗时；保留原回执不改写。374项Python四文件
命令27.90s与104项JS五文件命令2209.469833ms是共享命令总耗时，非各门独立时间，不累加为
总运行时长。主会话当前源另实际完成205路径Constraints（0.07097825s）、文档治理
（0.302463333s）和索引（0.866323584s），均exit0，采用工具实测墙钟时间。
完整特性范围05326b606..9d0e7909d另有immutable审查包；新独立审查代理最终Approve，
未发现可确认Critical/Important/Minor，不把静态代码批准当作Docker实测或MacCI通过。

## 历史公开入口失败及真实剩余项

dd9fec819 上进行了一次默认测试数据根的公开start负例（显式18088/13081）。
第一次env-i PATH漏掉/usr/sbin，缺lsof导致probe警告，属于控制器环境前置错误，不作产品RED。
补齐标准系统PATH后仅复测一次，实际exit1/runtime_ownership_unknown；无probe警告，未启动子进程，
canonical数据根仍只有原build-lock。日志native-canonical-start-{systempath-}dd9fec819.log。
未凭指定空闲新端口跳过旧默认产品监听检查，未停止日常服务。

同提交上再用公开RESEARCH_DATA_HOME选择真正不存在的native-live-data，正常系统PATH，
公开start同样exit1，但发生在安装门：dsh_runtime_lock_mismatch。
日志native-fresh-start-dd9fec819.log。start要求data_root/runtime/build-lock.json，而正常安装器
先创建该root再写build-lock；因此目前fresh单元fixture的installation-ready mock不能证明
公开fresh路径可达。未拷贝build-lock、移动/清空原root或修复manifest绕过该门。
这是 dd9 的历史公开入口缺口，随后 R5 已修复正常 auto-start 安装桥并以 b9ff 新 HOME 实测。
不把旧失败记录改成 PASS，也不把此实测扩大成所有自定义 root 场景已通过。

- 已完成修复均经过限定patch独立审查；9d完整特性分支最终只读代码审查Approve，后续物理启动发现新缺口，修复尚未完成。
- Native正常安装/健康/restart/stop/start-again已实际通过b9ff范围；efff成功会话/CSV创建，9d正常刷新/启动后持久化实际通过；Docker往返仍NOT_RUN。
- Docker完整镜像/安装9d实际PASS；macOS启动FAIL（staging别名缺口），其他生命周期、测试凭据权限及同根往返BLOCKED/NOT_RUN。
- 已停止、精确归属Docker容器自动更换绑定的非force处置：独立授权未收到，未实现、未删除。
- GitHub macos-14 clean install/health/Doctor：NOT_RUN；新分支push/PR/CI未获授权。
- Windows/Linux：NOT_RUN/交接，不归当前Mac任务验收；Ubuntu运行不算Mac证据。
- black/ruff/isort/mypy：所用环境无这些工具，未新增依赖、未伪称执行。

完整回执和最终HEAD范围将在实际验收后生成/校验。现有checkpoint回执只证明其记录的本地合同，
不替代真实安装、进程/监听归属、Docker Desktop或Mac CI。

## 981 精确源码实测与停止继续试补丁的依据

正常公开 `./setup-web.sh --runtime docker --no-start` 实际 exit0，code_commit=981e20f10，
接受镜像 sha256:be7d9daaf4fc7d5c7ba9697c9febbe8edb3526242cd9b8d6c998ae3643278648。
证据 `/private/tmp/rwb-macos-ports-live.3av1gO/docker-install-981e20f10.log`。
同一精确源仅执行一次 `rwb web start --no-open`，exit1/docker_start_failed；
证据同目录 docker-start-981e20f10.log。现有持久日志 research_workbench_20261006.log
行1603首次得到 reverse/post_yield/ancestor/parent/changed=uid,gid，行1605为
RuntimeStateError/runtime_probe，两个子进程返回码均null。早期初始化没有保证后续认证期间身份稳定。
不接受 reverse、循环重pin、吞异常重试或移出guard作为修复；不重复同源构建/启动。

独立规格/Python审查批准981限定补丁；独立安全审查无确认阻断发现，但均未认证真实效果。
局部实际六模块387 Python、JS/Docker104、八路径约束与文档门通过；真实启动失败优先于mock GREEN。
global runtime_state.py未因981改变。现有固定Compose/controller链是初始化的既有信任前提，
guest本身不独立证明bind mount归属或没有其他写者；容器up后实际mount核对不能被描述成up前证明。
只读复核上游ddc认证preload/handoff保留外层guard并增加认证写入，不是已证明的身份稳定修复。
如现有bind无法满足稳定身份前提，Docker专属运行状态存储方案及安装/mount合同需要独立范围决定；
本轮没有改为tmpfs/named volume、迁移state、改权限或削弱guard。

Docker失败后，先等待安装终态，再正常公开Native no-start刷新、runtime use native --stop-current、
start，均exit0，源仍981。Native Web53170/DSH53783 owned/ready；Doctor exit0：ok、installation_ok、
product_ready均true/无issues。首页与/static/app.mjs HTTP200，原成功session HTTP200/id与title相同/idle，
原附件HTTP200/39bytes/SHA47ad7335dab05dd4668880628ab1fdbee1f1fd9642a4cd160484f167353912eb。
RAM-only基线比较 tokens_preserved/other_fields_preserved/origins_match均true，无原值落盘。
证据同测试目录 native-{install,use,start,doctor,persistence}-981e20f10 对应实物文件。
此为Docker失败后的Native恢复持久性，不是成功Native→Docker→Native往返。

仍缺：真实Docker ready/Doctor/健康/restart/stop/start-again、Docker凭据及mount权限、成功跨模式数据往返，
最新master整合结果验收、GitHub macos-14安装CI。Windows/Linux保留NOT_RUN/交接，不阻塞Mac职责。
本地验收及整个goal均未完成，当前不能进入远端CI阶段；没有新增远端操作或环境权限。

### 当前完整计划与证据复用账

精确981原goal范围209路径（含三个主收尾产物），特性053范围69路径。两者均L4。
当前完整209路径Constraints、文档治理、Python索引各exit0，实测墙钟分别
0.164467792/0.150607041/0.855686167秒；logs/macos-goal-final-document-gates-981e20f10.json
及对应constraints/documentation/index日志可定位。受管内核11项SHA重新核对零漂移。

回执19个local ID的source-affinity如下；复合命令耗时不能逐ID累加，复用不意味着当前HEAD重跑：

- verification-policy/receipt/incremental-validation三个合同：复用efff的99项JS，复合4.307秒，
  logs/macos-goal-final-verification-contracts-efff4651a.log；kernel/policy/tests至981的git diff为空。
- service-manager/installation/api/runtime-mode四门：复用0b7的729项Python，复合231.93秒，
  logs/macos-goal-shared-guard-consumers-0b7c801cf.log；涉及源码和tests至981的git diff为空。
  后续2a共享guard仅日志分类，无条件/异常/权限改变；981 Supervisor另由当前闭包覆盖。
- local-integrations：复用efff的L1 Python复合853PASS/1原有skip/251.55秒，
  logs/macos-goal-final-l1-python-efff4651a.log；integration源码/test至981未变，
  后续guard日志不改变拒绝语义。不是完整853项在981重跑。
- critical-smoke：复用403协议19PASS/0.26秒，logs/macos-goal-final-l3-protocol-40375ee80.log；
  protocol test未变，认证/runtime由981六模块及实际Native补验，真实Docker仍失败。
- container-runtime/credential-backend/runtime-contract：当前981六模块387PASS复合26.36秒，
  .ai/reports/2026-10-07-docker-state-bind-initialization.md列出精确模块/命令。
- Docker/architecture/repository-cross-platform/full-L4四门：当前981五文件JS104PASS，
  复合2.354565417秒，同981报告；平台合同静态PASS不代表其他平台真机通过。
- Constraints/governance/index三门：上述当前981逐门实测时间及独立日志，不采用旧复制耗时。

回执初版validator拒绝false-escalation附带reasons，随后又拒绝把文字说明当证据路径；
仅修正回执metadata为合法空reasons及本报告regular-file引用，不改测试/旧证据/规划要求。
五个外部门均NOT_RUN，分别是project-constraints、research-web-checks、research-web-docker、
research-web-windows-verify和research-web-bootstrap；前三Linux及Windows保持平台交接，
Mac bootstrap没有新分支CI证据。总体receipt保持BLOCKED/mergeReady=false/releaseReady=false。

当前981 Native restart exit0，Web53170、DSH变为55044；stop exit0后两测试端口closed，
再次start exit0/两角色owned/ready且端口53170/55044，公开status exit0。
再次RAM比较控制token/其他字段/实际origin均true。日常3081PID68985/8088PID69730保持原实例。
最后正常停止任务Native，不删除任何测试数据、卷、镜像、分支或worktree。

## 2026-10-07 授权继续：私有 tmpfs 限定修复

人类独立授权Docker运行状态存储调整，并明确确认 `/state` 私有tmpfs、日志单独bind到
`/state/logs`、数据与凭据挂载不变、旧state保留不迁移、guard不放宽。设计/计划本地提交52b839036，
单一实现代理拥有挂载/controller/supervisor及相关测试文档；主会话仍拥有本报告与实际服务操作。
没有新增远端、全局环境、依赖或真实数据迁移权限。

一次无网络/无宿主mount/非root/只读镜像的最小实验使用既有981image，精确tmpfs覆盖镜像VOLUME路径，
在原strict outer guard内调用原ServiceManager auth writer/read三次，synthetic cookie只在临时容器RAM。
结果strict_outer_guard_passed=true、normal_auth_writes=3、parent_identity_stable=true、
parent uid/gid10001、mode0700、auth0600；没有打印cookie或其哈希。
证据 `/private/tmp/rwb-macos-ports-live.3av1gO/docker-private-tmpfs-normal-auth-proof-corrected.json`。
首个实验误用父路径/data tmpfs，镜像VOLUME仍自动创建/data/research-web，mkdir FileExistsError退出；
保留docker-private-tmpfs-normal-auth-proof.json，不算productRED。修正精确路径后exit0，测试容器自动移除，
不触碰已有数据、卷或实例。此实验只支持临时状态身份稳定，不替代正常stack/认证/生命周期验收。

Docker官方tmpfs文档说明停止后内容不持久，但Linux VM可能swap；不能声称秘密绝不落盘。
来源 https://docs.docker.com/engine/storage/tmpfs/ 。当前完整安装/生命周期仍等待实现与独立审查。

### 已冻结实现与当前源证据

86c85a390实现提交17拥有路径，binary diff(a316e2af6..86c85a390) SHA
e3e9bed779dede171a02b2d82cf8ad310a88c2e8b066b7ef2e7dd87ee1834b72，与主会话重算相符。
独立规格APPROVE；独立Python、JS/Compose、安全审查无确认阻断问题。JS发现03数据文档旧路径残留，
8e0d728fd只改该段及任务报告；复核LOW已解决，生产/测试/配置与86字节一致，不因此重跑785/203。
源runtime_state/auth/healthcheck/锁定义/Native均无本修复diff。正式785 Python/203 JS日志与测量仍归86，
命令、模块与初轮失败详见 .ai/reports/2026-10-07-docker-private-state-tmpfs.md。
主会话重新执行局部receipt validator：valid=true/BLOCKED/12local/4externalNOT_RUN，不伪造平台PASS。

主会话实际created和running临时容器均证明Docker29.8.2在Mounts中省略--tmpfs条目，HostConfig.Tmpfs
完整；/proc/self/mountinfo确认/state实际tmpfs。故正常容器与原control-preparer均按强制完整HostConfig
和严格可选显式Mounts校验，并保留精确bind来源/RW/nonce/image/cleanup合同。
证据同测试目录docker-private-tmpfs-{inspect-proof,running-inspect-proof,kernel-proof}.json，
对应精确临时容器已停止/移除，无宿主data/cred挂载，无真实卷或实例处理。

原goal4d6a4eff..8e完整212路径（含三收尾产物）、特性053..8e为74路径，L4/19local/5external。
当前完整212Constraints/治理/索引分别exit0/0.241388083、0.167487125、1.008997208秒，
logs/macos-goal-final-document-gates-8e0d728fd.json记录逐门工具墙钟，不把复合计时逐项重复相加。

### 真实安装的任务 fixture 前置拒绝

8e首次公开Docker no-start安装exit1/docker_data_home_unsafe，发生在构建前，未调用APT或镜像build。
只读定点元数据确认此前旧测试镜像生成的任务state/logs为0755；其当前用户归属、真实目录与父级700
均可核对，但新源正确拒绝这个非私有叶。证据docker-install-8e0d728fd.log；不是产品网络RED。
仅收紧这一精确、已证明属于本任务的临时日志目录到0700：nofollow保留FD验证同inode、UID/GID
不变，不修改文件内容、认证、产品资料、日常实例或全局配置。证据test-only-legacy-logs-permissions.json。
这是显式测试fixture前置处理，不是生产源自动权限修复或旧用户安装升级PASS；生产仍拒绝0755目录。
原拒绝保留，实际日志bind目录inode不迁移/不删除，oldstate/runtime原样留存。

在这个明确变化的fixture输入下，公开安装器只复验一次：docker-install-8e0d728fd-private-logs.log，
同进程session13030，已越过private-home检查、实际APT和固定DSH/pnpm锁定依赖阶段。当前仍运行，
不计accepted image或新Docker生命周期通过；不新起同原因重复build。RAM控制token/其他字段/Native53170
origin比较仍true，无秘密快照/原值/哈希落盘。

### 私有 tmpfs 镜像与真实生命周期结果

8e公开安装最终exit0，接受sha256:6d73814420875aeb7ddd13e10c72689361d75212e1f27cc5767065afc6fd1ea4。
同源码首次start exit1，已越过runtime_probe，stage=web_wait、Web退出3、Runtime仍alive；
不再是原state UID/GID失败。既有私有child日志定点堆栈为mcp_registry/sync的HTTPX代理初始化，
稳定分类确认ImportError/optional socksio not installed。任务专属Docker config原为构建注入HTTP SOCKS；
Docker也把这项default proxy注入容器。未安装socksio、未改锁/TLS/全局代理，只把本任务HOME
.docker/config.json的httpProxy换成既有HTTP host.docker.internal:29758，https/noProxy不变。
环境输入有具体变化后仅复验一次same accepted image start：exit0/owned/healthy。

Host Web自动选62914；internal DSH3081、不发布，日常8088/3081保持原PID。公开status、Doctor exit0，
Root/static HTTP200；原session106746f3-4612-4192-a69f-b49b6bea2743 title相同/idle，原CSV附件HTTP200，
39bytes/SHA47ad7335dab05dd4668880628ab1fdbee1f1fd9642a4cd160484f167353912eb。控制token/extra字段
与RAM基线相同、origin内部8088正确。没有配置模型key或发送模型请求。

幂等start exit0；普通restart exit1/runtime_force_required（预期安全负例，不改合同）。在同一个仅有
测试会话的owned实例上执行文档显式restart --force --no-open，exit0/两项healthy，数据UUID/CSV哈希保持。
web logs --tail100 exit0。stop exit0/exited，host62914 closed；start-again exit0/owned/两项healthy/62914。
幂等start回执尚未终态时启动了readonly no-force restart负例，这是控制器顺序瑕疵；随后实际force
restart/stop/start-again均等待前序终态，没有把重叠负例当严格串行生命周期证明。

真实Docker Desktop容器（actualID ce90e3103452da75b1a3b3ac7baf3cb52254db9f679358267c0220d6463bbb4a）
inspect绑定安装ea585/image6d：三个bind、精确tmpfs声明、仅Web发布。实际kernel确认/state tmpfs，
runtime目录700/auth600/当前UID10001。原PrivateFileCredentialBackend synthetic服务账户set/get/delete
真实通过：root700/record600/nlink1/owner当前UID；没有访问系统Keychain或供应商。第一条exec误把
Doctor的脱敏ownership_id fingerprint当actualCID，NoSuchContainer是控制器参数错误，保留原文件，
不是实例漂移；按安装label取actualID并核对image后纠正，metadata/权限证据后缀correct-id。

另一个独立dummy凭据留作持久化：Docker→Native --stop-current exit0；公开Native锁定no-start刷新1872
与start exit0/53170+55044 owned/ready，session/CSV重新读回200/hash相同，controls origin53170/token不变。
Native→Docker --stop-current exit0，1872 host controller通过原已接受8eimage start exit0/62914+internal3081；
session/CSV再次一致，dummy凭据原值回读相同后经原backend删除成功，controls origin8088/token不变。
这不是秘密跨模式迁移：两个backend根独立，dummy只留在Docker私有根；记录仅布尔和模式，不含值。

真实首轮Docker相关日志位于原task目录docker-{install,start,status,doctor,persistence,...}-8e0d728fd
对应实物；proxy修正start后缀http-runtime-proxy。restart、stop、start-again、root/static/fixture文件与
permissions/layout-correct-id明确区分。1872是host Doctor常量一行投影修复state=tmpfs/logs=bind，
schema1及verified实际inspect规则不变，非guest运行行为；独立spec/Python质量批准、3RED→322controller
及19protocol/104JS通过。binary diff8e..1872 SHA7b1adb64773f608bbd81ea37ef8b4a601438e6808e2678d09f6aa402e81af3d7。
app/research_web、docker/、Compose、Dockerfile和依赖与8e字节一致；复用上述不受影响的guest镜像与生命周期，
不宣称1872镜像已经重建。1872真实Doctor现在volumes state=tmpfs/logs=bind/verified=true，ok=true。
Native1872正常安装/启动和活动切换另有本提交实测证据。最终回到Native及任务停止正在按串行入口完成。

剩余必要门：最新master合并结果及受影响本地验收、同平台GitHub macos-14安装CI。新分支暂无远端授权，
不push/PR/merge/tag/dispatch/rerun/cleanup；其他平台NOT_RUN/交接不归Mac职责。当前不能标整个goal完成。

最后Docker→Native --stop-current、Native start、最终session/CSV读取、Native logs --tail100、Native stop
均exit0；final-roundtrip-persistence-1872bbc2c.json为同UUID/39bytes/同SHA的实测。最后53170/55044/62914
均closed，日常3081PID68985与8088PID69730未动。Docker stopped container保留，所有旧test资料、镜像、分支、
worktree保留；synthetic凭据已由原backend删除。尚未使用新空白HOME实测首次control-preparer创建，
其真实Engine表示已实测、原creator与身份/cleanup单元覆盖通过，但不能把这些写成独立fresh-Docker安装PASS。

本地 Task13 本轮冻结源码实测已覆盖安装、两项运行/Doctor健康、HTTP资源、restart、stop/start-again、
活动双向切换、同资料往返、独立文件凭据与实际mount权限，证据与上述未执行项区分。
Task14仍需按新受管feature和integration worktree合并最新master，并重新规划/验证实际合并影响；
controller不支持adopt或仅记录verification，不能手工写receipt或通过publish伪造本地进度。

### 1872 完整范围回执（非集成结果）

原goal全212路径、L4、19 local IDs/5 external IDs；validator exit0/valid=true/BLOCKED，mergeReady和
releaseReady仍false。局部fresh-Docker空HOME、最新master整合/同平台CI和停止容器换绑定处置等未证项保留。
212路径当前Constraints、文档治理、索引实际各exit0，逐门墙钟0.163617792/0.150268959/0.904164417秒，
logs/macos-goal-final-document-gates-1872bbc2c.json。不是旧206/209路径记录。

本轮19 local ID证据投影：policy/receipt/skill/repository四合同复用86的203项JS组合4.893245375秒；
Docker/architecture/full-L4三门采用1872选中JS104组合2.368301583秒；mode/controller门1872组合322项
20.10秒；protocol门1872 19项0.42秒。container/credential/runtime-contract/installation四门复用
86最终785项Python组合58.79秒（具体十模块在其报告）；1872只改host Doctor常量，guest/安装/认证消费者
输入字节不变，scope相应覆盖，不说整785项在1872重跑。Service-manager/API复用0b7的729项组合
231.93秒，local-integration复用efff的853项组合251.55秒/1原skip；原代码/tests与相关Native/数据输入
仍未改变，新的Docker/controller影响另有785与322及真实模式往返覆盖。以上复合耗时重复引用不累加。
完整镜像与guest实测仍归8e；1872实际host Doctor及Native安装/模式切换另有当前源命令证据。
只修改本轮回执投影，不改任何旧回执，最终integration必须重新按真实合并影响审计适用性。
