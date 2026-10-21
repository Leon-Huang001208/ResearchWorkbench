# 独立常驻发布仓库身份修复

macOS Mac mini，Web 部署安全修复。用户持续明确授权合并与部署；数据、配置、凭据和会话保留，活动/未知等待，失败回滚。

真实部署在首个 source_common 检查阻断，未建立 journal、停止服务、安装 wheel 或读写凭据。根因是常驻 primary 为独立 GitHub clone，而 gateway/source 共享开发仓库；原工具错误地要求恢复角色也共享 source_common，并从 primary 建立冻结源码 worktree。

修补逐角色保存 canonical common directory/inode，验证精确 GitHub origin，apply/安装/恢复共同复验；source 仍必须匹配权威 source_common，冻结源码从 source 创建。停机前 readonly cat-file 确认各角色已有目标对象；不移动发布目录或改部署配置绕过。

先新增三项回归并观察 AttributeError RED；真实临时三仓库及换源/common/inode负例转绿。再补真实独立 clone 的完整 validate_state 及实际替换 .git inode 负例，103 项部署合同通过；apply 也在发布栅栏前执行完整恢复身份验证。独立审查复跑 103 项并 Approve。
Router 维持 L4，112 项 JS 架构/文档/跨平台合同、本机完整 changed-set 约束、文档治理、Python 索引、Ruff/Black/isort 与目标 mypy 通过。只读真实角色身份预检 primary 独立、gateway 共享均通过。
中途测试 fixture 放置及目录权限错误曾失败，修正后重跑，不隐藏失败日志。无依赖安装、无模型调用；真实服务仍是原版本，不能宣称已部署。CI 和真实切换尚待执行。

候选 915fb4fa 的 Mac Bootstrap/Constraints 通过；Checks 首次在 Python 1185 项通过后的 JS 尾段触及 20 分钟上限，同一候选重跑后 1185 Python、734 JS、10 editorial 全通过。但主线期间合并 PR168，PR 合并冲突门正确阻断。
对其五份导航 JS 做独立兼容审查：不改后端/依赖、模型配置或凭据 API、会话控制器与发送/停止门；保留旧路由和 manifest 交接，无阻断。固定产品基线推进至 4e8be6ac，并保留导航与本任务双方文档。已有升级测试注册在新基线时不重复插入，增加失败回归后验证。新合并树须重新通过三项 CI，不能复用旧树的整体验收。

最新树Checks再次在Python全部通过后的JS阶段触及20分钟墙钟上限；对比五个实际成功job耗时838–1152秒及两次取消，原预算无足够波动余量。只将同一标准job时限扩至30分钟，保留所有测试/检查、runner及平台门；scope只承认这一个确切工作流差异，新增20/45分钟拒绝反例。没有通过缩减验收换成功。
完整项目约束随后识别其有界 workflow 文本仍是旧20分钟，已同步为30；其余必需规则未改变，操作员仅接受该配置文件的一个确切文本替换，并增加删除其他规则/45分钟拒绝测试。
2a0ca21d 的三项CI全部通过，但期间主线合并PR170，对同一操作员补充导航全量身份检查；已保留该更严格逻辑及9项回退/来源/模式负例，并与本次独立仓库、完整恢复预检、30分钟有界预算和所有门合并。核心模型产品回到其独立固定0d73c034，导航固定4e8be6ac；五文件即使从差异消失仍逐一核验，未覆盖另一任务修复。新树仍须完整重验。
现场随后确认：另一已授权事务已完成 c68814db 主实例与网关升级，model-upgrade-result 为 deployed/preserved=true，无剩余journal。独立GET核验模型服务脚本与该Git版本逐字节相同（SHA256 1c8070d8e125dbe6b872dd9f4a87d71901880fc7990bfc04ef0faa477a95528a），DeepSeek/Flash原配置与系统Keychain凭据存在状态保持，单一活动profile正确，原生/Host空闲、私有池为空且私网HTTPS健康无栅栏。模型服务页已生效，不重复运行只接受旧5df基线的桥接事务以免退回现有版本；本PR仅补齐操作员及CI安全源，仍须最终树全部检查后合并。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"保留原主实例和网关部署节点，分别锁定已有发布Git身份；不改变单DSH、服务管理或自动兼容范围，独立clone不迁移。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"只修补已有联合事务的源码权威与发布角色身份区分，用户池、出生栅栏、HTTP冻结、保全与恢复拓扑均保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"依据实际job耗时将原Checks单job时限20分钟扩至30分钟；测试、runner、步骤、并发与Mac安装门均保持，不新增执行节点、依赖或模型调用。","diagrams":[]} -->
