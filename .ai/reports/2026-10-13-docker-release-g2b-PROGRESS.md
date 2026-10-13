# G2B 可追溯制品与受管晋级/回退

architecture-review: updated

<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"增加冻结制品、接受事务与五卷凭据的管理员部署边界，更新同一部署图，不增加研究引擎。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有BFF与DSH执行拓扑不变，维护在原任务准入前串行控制，版本API只读取安装身份。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"仍由既有Automation调度与执行，维护仅暂停受理并等待原工作，不新增调度器或任务事实源。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"原生报告执行和产物投影不变，维护覆盖已有scheduler和worker，未改变能力或报告持久格式。","diagrams":[]} -->

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
| implementation | IN_PROGRESS |
| local_release | NOT_RUN |
| stage_acceptance | NOT_RUN |
| promotion_rehearsal | NOT_RUN |
| rollback_rehearsal | NOT_RUN |
| registry_publish | NOT_RUN，缺独立授权与明确认证条件 |
| registry_digest_pull | NOT_RUN |
| real_supplier_for_this_artifact | NOT_RUN，本轮不索要 Key、不重复收费生成 |
| daily_production_deployment | NOT_RUN，明确排除 |

## 证据与后续

所有实际命令的私有 stdout/stderr 位于 ~/.local/share/rwb-docker/logs/g2b/；
管理日志为 logs/manager.log 与 logs/release.log，只记录稳定分类、不输出秘密。
下一步冻结首个已验证源码 SHA，完成真实封存与 stage，再实施晋级/回退及失败演练。
release.json、独立接受回执和部署事务分别保持版本身份，不把新证据提交冒称实测镜像源码。
Windows/Linux 产品 dispatch 与原生验收由对应真机接手；本轮 Mac 不伪造这些 PASS。
