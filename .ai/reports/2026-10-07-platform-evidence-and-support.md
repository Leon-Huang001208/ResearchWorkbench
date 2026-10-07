# 阶段二、三：平台任务证据与能力边界

## 当前状态

宿主 macOS；阶段二与 Mac Native 功能开发切片已完成。用户明确授权全部阶段、推送与合并，并确认目前只有 Mac；Windows/Linux 原生与其 CI 保留交接。阶段三 Mac Docker Desktop 由独立 task-20261007-bda2aa87e13e 接续，不借 Native 通过认证 Docker。

- taskId: task-20261007-ffa331322bc9；分支 codex/task-20261007-ffa331322bc9-platform-evidence-and-support；基线 c24a8a161674678d572bf9ac35fab30489b40605。
- 正式共享框架已发布 f853b1b268a1b39c537136d867ddf5a570f9730e；Framework Checks 37573888876 SUCCESS；集成合同 308/308 PASS。Project runtime 正式 preview/apply/verify，无 drift；policy3/plan4/receipt3，不手改分发文件。
- 协议保留全部 changed set、宿主任务、平台交接和整体门禁；CI 需真实 runner、候选及 checkout 身份，merge preview 校验真实 Git commit 有序父提交。旧真实版本升级/回滚并实际加载旧库通过。
- 原有阶段一报告的当前状态已收口；历史旧 receipt 保留原 BLOCKED 身份，另存长期交付摘要，不将旧未绑定回执涂改 PASS。
- GitHub master protection 已实际 PUT 后 GET 复核：strict=true、check/GitHub Actions app15368、admins=true、PR required（审批数0）、禁止强推/删分支、discussion resolution=true。rulesets 仍为空；平台条件门由任务证据校验，不宣称 GitHub 全部强制。证据 logs/platform-delivery/branch-protection-applied.json。
- Windows/Docker 范围和原有条件门已按新授权恢复；Windows/Linux workflow 仍由对应设备 exact SHA dispatch。
- 能力切片 578 个不同 Python目标 PASS；Doctor 三链共用轻量状态，validated=false；Windows 文档 501、非 Mac 沙箱 unsupported、Windows Docker ACL 未验证阻断，Docker 旧本机集成 status 保留。
- 旧 Docker 大文件有既有 Black/isort/Ruff 基线问题，本任务不将整文件风格标 PASS；新模块/文档读取/新增测试及相应格式和类型检查结果见 logs/stage3/capabilities-validation.md。
- 阶段二/Native 候选及合并提交 `205d2a170d9ece9c2751e014b63abe326510ab9c`；[PR #83](https://github.com/Leon-Huang001208/ResearchWorkbench/pull/83) 已合并。Mac Bootstrap 37587972966、Project Constraints 37587972944、Web Checks 37587972950 SUCCESS，实际 checkout 为 `4bd5a6d8660ba7072da37878ce73396b8370fbab`，有序父提交 c24/205 已核对。Native 独立安装、owned ready、重启、沙箱及阅读链路实际通过。
- 正式 plan4/receipt3 与摘要已由候选现场验证：hostAcceptance PASS、aggregateAcceptance NOT_READY、mergeReady/releaseReady false。Windows NOT_RUN，Linux 因 Docker CI 未运行为 BLOCKED；不把已授权的 Mac PR 合并写成跨平台发布就绪。归档 `2026-10-07-platform-evidence-native-*` 明确只认证候选205，报告后续提交身份另记。运行实例未更新。
- 交付控制器 P1 恢复校验及失败分类修复已正式发布 a293d755ff162f294f1efff4bef67b90ec915432，314固定合同与 Framework CI37586440387 SUCCESS；项目受管核心仍为已核验f853（此次控制器修复不改分发库）。

## 映射与图证据复用

frameworks、integration-coordinator、本机集成与 verification-workflow 使用精确源码归属。研究协议修改无需框架/协调/Tabbit 无关章节；每个受影响 owner 仍必须改说明、提供结构审阅，结构 changed 仍必须改已登记图源。不存在降低未映射或必需图证据门。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新增Doctor能力实现状态投影，不改变Native双进程和Docker单容器、数据及凭据挂载关系；安全阻断保持。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Doctor新增固定无秘密能力字段，不改变研究HTTP/SSE、DSH调用与服务进程关系。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"安全POSIX读取缺primitive时显式501，不增路由或文件浏览能力，既有允许列表和opaque CSP保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"任务和证据身份字段补入既有planner与receipt，规划依然只读，图中源码映射和验证交付流程关系未变。","diagrams":[]} -->

必需图源/HTML/审阅输入未改变，复用已登记哈希证据；生成索引和阅读卡片随精确映射更新，源码快照与产物交付提交分开记录。真实模型、厂商授权、Windows目标版本、Linux原生与两架构 Docker CI 待对应设备任务，不用Mac容器结果替代。

## 实际网络故障与定点修复

Mac Docker 构建的直连认证超时，现有系统代理匿名认证HTTP200；显式代理后APT HTTP大包仍中断，未标安装通过。同一GCC包经HTTPS完整下载16300644字节、HTTP200、29.435秒；固定Python基础镜像已有CA bundle。Dockerfile两个APT阶段改HTTPS，保留签名/原包/固定镜像，无TLS bypass。新增固定合同先RED后GREEN；重新镜像构建结果另记。Native独立安装/start/Doctor/重启、沙箱实际执行/会话外写入拒绝及非秘密数据保留已通过。当前新增门禁检查为271通过、1项原生Windows专属跳过，该跳过不认证Windows。
