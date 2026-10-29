# 精确维护作业身份 v3

宿主：macOS；任务：Web 维护合同开发；范围：独立源码交付，不操作生产服务。
任务 `controlled-job-identity-20261029-569b85cd`，基线
`270644bf1513e65c50859fb2e3baec6ce06ccfef`。

## 变更与边界

新增只读 `ExactJobBinding`、最近合同测试及独立维护文档。生产固定原 root/label/port；
私有目标从真实 0700 根、0600 登记、外部已审 nonce/路径/摘要派生，拒绝任意 label 和
artifact 漂移。保留 venv argv alias。身份不授予效果权限、不分配端口、不注册服务，
不改 DSH、旧控制器、其他聊天源码、业务数据或模型配置，没有新增依赖。

## 已执行证据

- 受管 Harness 与 Git check/start；fsck 通过，独立 worktree，从最新 master 开始。
- 首次环境缺 pytest，改用已有批准缓存，没有安装包；随后缺模块 RED。
- 初始 3 例 GREEN；实际反例暴露 nonce 类型与 plist 重定向问题后修复。
- 独立已审摘要为空的 2 个 RED 已修复；独立 SPEC 又发现跨文件重验窗口，先实际复现
  script/registration 两例 RED，再加最终 no-follow stat sweep，43 例分 18+19+6 通过，
  JUnit 为 `logs/job-identity/*-specfix.xml`，零失败/错误/跳过。
- 首次独立 SPEC 复评 PASS、Python QUALITY APPROVE，绑定 source `e00a5313...` 与
  test `790dd391...`；随后仅区分 directory/file 循环变量名修复 mypy 类型推断，43例及
  mypy已重过，最终候选另行复核。评审未冒充运行真实 launchd 或完整维护。
- Ruff、Black、isort、项目 mypy 近处检查通过。首次 Black/mypy 缺缓存依赖等环境失败均保留；
  只定位既有批准缓存补足工具搜索路径，没有安装包。既有 pytest asyncio 配置 warning 保留，
  此处全部同步合同执行，无异步跳过。

原 Checks 同一步登记新回归，原 Mac Bootstrap 安装检查增加无效果的模块导入，未增 job/
runner/依赖/timeout。完整 changed-set Router、源码 CI 与同候选 Mac 检查尚未在本报告时点完成。
本地首轮完整11门为10 PASS/1 FAIL；失败为README复核、两份模块文档及verification-workflow
结构决策缺失。原FAIL回执保留，补文档后约束检查已通过，最终新候选仍需正式重验。
真实 launchd、完整 apply/resume、旧实例退役、Wind/Office 与部署均 NOT_RUN；Windows/Linux
产品验收 NOT_RUN。此源码任务的通过不能提高旧 b800 现场资格。

## 后续独立物理原语验收（同日追加，不改写上述时点）

最终已发布源码候选 `a582267b8611b2be9334e68de87613290672e961` 的完整本地 11 门已通过；
macOS 干净安装 CI `40845740831` 通过，实际 checkout `c9464bca330026c5aafb2241f586dd5f949c6197`
的双亲及 tree 已与该候选核对。Checks `40845740855` 因原 45 分钟上限取消，保留失败，
不能用 Mac 安装成功替代；尚待正常性能修复基线与新候选验收，不重跑空候选或延长时限。

另一个受控维护验收任务实际使用的本模块 SHA-256 为
`de2d09a1d8bf470ae85ca8b99e6f12f78bf6e81cd10483cd2c74b7664c6c6ca7`，
与本源码完全相同。其私有作业原语在真实 macOS 27.0.1 / arm64 / 24 GiB 完成：
一次 bootstrap、nonce 健康检查、一次精确 PID/birth 的正常 TERM，确认 exit 0、完整
`ready → term_observed → closed`、PID 消失和端口关闭后才 bootout；15 次 launchctl 均已回收。
独立最终只读复核再次确认目标缺席、PID 消失和端口拒绝连接。没有强杀、enable/disable、
供应商、Office、真实模型或生产动作。完整 51 条事件摘要为
`0186e2992c1159b9dc0ab02309bb3f6dd86da62f640318a1d210f9de380abe17`。

原语所用驱动/计划经过独立 SPEC 与 Python QUALITY，最终 20 项纯函数测试和固定 Python
只读预检实际通过。其早先两个真实失败均在 bootstrap 前，源码、计划、批准、完整日志及
原流保留；只有精确未提交证明核验后显式创建新 epoch 续跑，未重发已受理或未知效果。
完整原始证据及字节/权限恢复验证留在本地受控备份中，不提交包含本机域信息的原流。

这些证据只认证本模块在私有维护原语中的一次真实使用。App 映像、真实 kernel argv、
loaded policy、审批、排空与退役等仍由调用上下文独立核验；本模块本身不授予效果权限。
完整 RWB apply/resume、旧实例首次准入/退役、外部 Wind 清理、生产切换与认证页面仍未在
该原语任务完成，历史清理失败维持 UNKNOWN；不得据此提升其资格。Windows/Linux 及
Docker 产品验收未由该原语执行，原未验证状态保留。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","diagrams":[],"reason":"仅增加维护内部只读目标身份与文件合同，不新增运行节点、服务、执行循环或DSH权限；实际生命周期仍由现有维护上下文承担。"} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","diagrams":[],"reason":"只绑定原生产网关或已登记私有演练目标，不新增账号或权限通道，不把target identity当作效果authority或旧实例证明。"} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","diagrams":[],"reason":"复用原Checks Python步骤登记只读合同回归，并在原Mac安装检查追加无效果模块导入；runner、job、触发频率、依赖、超时和原有验收断言均保留。测试与源码CI只认证各自冻结候选，实际launchd、完整CLI、退役和Wind保全继续由独立现场证据验收。"} -->
