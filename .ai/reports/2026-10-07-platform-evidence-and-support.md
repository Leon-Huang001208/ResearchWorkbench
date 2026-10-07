# 阶段二、三：平台任务证据与能力边界

## 当前状态

宿主 macOS；任务为 feature-development；本平台范围为共享验收协议、Research Web 能力投影、macOS Native 和独立 Mac Docker Desktop。用户明确授权阶段二、三及推送/合并；Windows/Linux 对应设备信息尚缺，原生适配与 CI 保持交接，不冒充支持。

- taskId: task-20261007-ffa331322bc9；分支 codex/task-20261007-ffa331322bc9-platform-evidence-and-support；基线 c24a8a161674678d572bf9ac35fab30489b40605。
- 正式共享框架已发布 f853b1b268a1b39c537136d867ddf5a570f9730e；Framework Checks 37573888876 SUCCESS；集成合同 308/308 PASS。Project runtime 正式 preview/apply/verify，无 drift；policy3/plan4/receipt3，不手改分发文件。
- 协议保留全部 changed set、宿主任务、平台交接和整体门禁；CI 需真实 runner、候选及 checkout 身份，merge preview 校验真实 Git commit 有序父提交。旧真实版本升级/回滚并实际加载旧库通过。
- 原有阶段一报告的当前状态已收口；历史旧 receipt 保留原 BLOCKED 身份，另存长期交付摘要，不将旧未绑定回执涂改 PASS。
- GitHub master protection 已实际 PUT 后 GET 复核：strict=true、check/GitHub Actions app15368、admins=true、PR required（审批数0）、禁止强推/删分支、discussion resolution=true。rulesets 仍为空；平台条件门由任务证据校验，不宣称 GitHub 全部强制。证据 logs/platform-delivery/branch-protection-applied.json。
- Windows/Docker 范围和原有条件门已按新授权恢复；Windows/Linux workflow 仍由对应设备 exact SHA dispatch。
- 能力切片 578 个不同 Python目标 PASS；Doctor 三链共用轻量状态，validated=false；Windows 文档 501、非 Mac 沙箱 unsupported、Windows Docker ACL 未验证阻断，Docker 旧本机集成 status 保留。
- 旧 Docker 大文件有既有 Black/isort/Ruff 基线问题，本任务不将整文件风格标 PASS；新模块/文档读取/新增测试及相应格式和类型检查结果见 logs/stage3/capabilities-validation.md。
- 本平台当前尚未闭合最终候选 CI/真机使用；hostAcceptance: NOT_RUN；aggregateAcceptance: NOT_READY；PR/merge: 尚未；运行实例未更新。

## 映射与图证据复用

frameworks、integration-coordinator、本机集成与 verification-workflow 使用精确源码归属。研究协议修改无需框架/协调/Tabbit 无关章节；每个受影响 owner 仍必须改说明、提供结构审阅，结构 changed 仍必须改已登记图源。不存在降低未映射或必需图证据门。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新增Doctor能力实现状态投影，不改变Native双进程和Docker单容器、数据及凭据挂载关系；安全阻断保持。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Doctor新增固定无秘密能力字段，不改变研究HTTP/SSE、DSH调用与服务进程关系。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"安全POSIX读取缺primitive时显式501，不增路由或文件浏览能力，既有允许列表和opaque CSP保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"任务和证据身份字段补入既有planner与receipt，规划依然只读，图中源码映射和验证交付流程关系未变。","diagrams":[]} -->

必需图源/HTML/审阅输入未改变，复用已登记哈希证据；生成索引和阅读卡片随精确映射更新，源码快照与产物交付提交分开记录。真实模型、厂商授权、Windows目标版本、Linux原生与两架构 Docker CI 待对应设备任务，不用Mac容器结果替代。
