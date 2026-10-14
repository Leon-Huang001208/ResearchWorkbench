# G2B 可追溯制品与受管晋级/回退

architecture-review: updated

<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"增加冻结制品、接受事务与五卷凭据的管理员部署边界，更新同一部署图，不增加研究引擎。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有BFF与DSH执行拓扑不变，维护在原任务准入前串行控制，版本API只读取安装身份。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"仍由既有Automation调度与执行，维护仅暂停受理并等待原工作，不新增调度器或任务事实源。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"原生报告执行和产物投影不变，维护覆盖已有scheduler和worker，未改变能力或报告持久格式。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"合入依赖保留模型来源的既有状态显示；维护503沿用错误提示，无新增页面、组件、主题、断点或框架交互拓扑，版本身份由管理员只读验收。","diagrams":[]} -->

## 范围与基线

Mac mini / Docker Desktop / linux-arm64。依赖未合并草稿 PR96 的完整提交
85831c7d70c89fb86fff4b220b5598aa1fe6c67c；本轮实时核对其三个 CI 均 SUCCESS。
独立 worktree 为 docker-release-g2b，分支 codex/docker-release-g2b。
没有取消 #96 草稿、合并、tag、GHCR 发布、VM 调整或日常生产操作授权。
交付包含独立可审阅 PR；生产、多人、公网、任意代码 Linux 沙箱和完整备份不在本轮。

## 实现路线

1. 管理根外部状态与源码分离；完整 Git SHA archive + source tree hash 冻结输入，复用固定 DSH staged payload。
2. 标准 Docker archive 及单一 Config/diff_ids/平台/角色验证；封存构建记录，独立 stage 接受回执。
3. 固定控制器与 launcher 内容身份；只读 plan、复核 apply、版本 status、上一接受版本 rollback。
4. 持久维护闸门覆盖 Web、Automation 和报告调度/执行/续跑；原生主/子任务及本地工作排空。
5. 独立 purpose=rehearsal 的 prod 五卷与一次性 AES-GCM 身份；同目标保留卷与身份，不复制 stage。
6. 两个内容不同的正式制品完成真实封存/导入/stage/R0→R1→R0；合成数据和桥解析持久化。
7. 故障/并发/中断夹具不进入正式应用制品；不收费调用，不凭 Docker healthy 宣称空闲。
8. 必需本地安装/最终提交 CI、独立 PR、资源收尾与逐项完成审计。

## 已执行与当前状态

VM 8319238144 bytes；外来 probe 保持 480MiB、CPU1、PIDs128、运行中。
G2A dev 经正式 stop/cleanup 退休名额，保留旧源码/四卷；G2B dev 正式 register/up，
绑定新 worktree，3GiB/CPU2/PIDs256，无 Docker socket。61GiB 余量初始磁盘检查。
没有全局 prune、批量删卷或外来资源停止。

相关管理器第一闭包 26 PASS；维护/API 回归 7 PASS，58 deselected；归档/事务/维护 13 PASS。
Ruff/Black/isort 已针对输入变化执行；最终完整影响面、类型检查与 receipt 仍待收敛。
初版缺模块的 red、fsync red、archive red、类型与参数失败保留私有日志。
一个新增 API worker fixture 误让 BlockingPortal 等待 Task，已精确终止本任务 pytest 并修正；
没有停止业务容器或其他任务。修正后的同一用例通过。

只读审查发现并已修正：恢复入口后的失败不自动强停；报告 runtime 任务表/调度门遗漏；
pending 持久化失败不在重启时开放；导入前 archive Config 绑定（不能靠 daemon 旧 image 冒充）。
源码/制品当前仍为开发与验证阶段；下表不将实现测试当真实演练。

| 项目 | 当前状态 |
| --- | --- |
| implementation | 实现与合并后本地闭包已通过；最终 CI 尚待本轮最终提交 |
| local_release | PASS：r0d/r1/r1a/r2 均真实封存、验证和导入，来源分别记录 |
| stage_acceptance | PASS：r0d/r1/r1a/r2 各有实际验收回执 |
| promotion_rehearsal | PASS：r0d → r1a，同 stage image ID，无二次 build |
| rollback_rehearsal | PASS：r1a → r0d，合成数据与私有模型桥解析保留 |
| registry_publish | NOT_RUN，缺独立授权与明确认证条件 |
| registry_digest_pull | NOT_RUN |
| real_supplier_for_this_artifact | NOT_RUN，本轮不索要 Key、不重复收费生成 |
| daily_production_deployment | NOT_RUN，明确排除 |

## 证据与后续

所有实际命令的私有 stdout/stderr 位于 ~/.local/share/rwb-docker/logs/g2b/；
管理日志为 logs/manager.log 与 logs/release.log，只记录稳定分类、不输出秘密。
2026-10-14：已完成上述实际晋级、回退、候选失败恢复及维护期间控制器中断。
中断只 KILL 本任务管理员控制器；旧写者继续且新 POST 收到 503，重复 apply 拒绝
unfinished_transaction_recovery_required；显式恢复和最终资源收尾仍以 HANDOFF 为准。
合并后相关 Python 闭包 335 PASS / 3 SKIP，JavaScript 必需闭包 128 PASS，
Ruff/Black/isort、新增发布/维护的 mypy、完整 changed set 项目约束均通过。
已合入 G2A ca0249f（含 master 0cf38ff）；新凭据格式源身份不同于历史 r0d/r1a，
兼容性未知必须拒绝直接切换，不能放宽门或把历史验收冒充新制品验收。
新集成制品 r2 已独立 stage PASS；向历史实例 deploy-plan 实际拒绝兼容性未知。
中断 recovery 完成后已受管停止演练目标。下一步完成故障拒绝剩余回执、最终 CI 与独立 PR，
不合并或更新日常生产；外部 probe 持续运行。
release.json、独立接受回执和部署事务分别保持版本身份，不把新证据提交冒称实测镜像源码。
Windows/Linux 产品 dispatch 与原生验收由对应真机接手；本轮 Mac 不伪造这些 PASS。
