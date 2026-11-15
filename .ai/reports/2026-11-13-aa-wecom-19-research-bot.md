# Research Bot 迁移与验收

## 实现与交付范围

用户确认采用 RWB 内置研究模式。原始调研和执行回执在本机留存。交付分支以 GitHub 同一基线建立，逐文件核对已验证候选。

- 接入现有 Automation、账号 Store 和 DSH。专用入口管理 Bot 及其间隔，通用日程和 Claw 入口拒绝变更与试跑 Bot。
- 新建和编辑后的定义保持停用。运行锁定定义版本、模型和显式研究工具，并在原生提交前记录会话身份与冻结资讯。已验证原件退窗时不会产生新模型调用。来源不可核验、受理未知和技能回执缺失有独立错误。手动运行使用持久请求身份，同一版本和请求标识重放只读回原运行。Workflow 已冻结的关联技能在同一原生白名单内。
- 主导航使用独立图标。列表读取最近运行摘要，历史分页读取冻结资料。编辑器保留无效输入以便更正，状态区分已受理、重叠跳过和版本阻断。
- Doctor 投影当前配置条件，实际模型与 DSH 执行能力独立验证。完整发布与本机验收分别记录。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"Research Bot 使用现有 Web 壳、模块导航和同源 API，新增模块位于既有 UI 节点内。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"专用 Bot 路由及 Doctor 状态均在现有账号 Host 内，同源认证和服务模式准入沿现有节点执行。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Research Bot 的间隔、冻结 Run 与结果沿现有 Automation、Store 和 DSH 连线，不改变执行拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"私网 Doctor 投影 Bot 的禁用状态，账号后端仍由既有私网服务管理。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"Research Web Checks 原分批及 Mac Bootstrap 原验收步骤新增专项用例和静态资源核对，现有 CI 作业与 runner 保持。","diagrams":[]} -->


### 续办验证与交付状态

- 共享 Web 测试环境按指纹复用。Python 专项 31 项通过，覆盖 Bot 运行身份、通用日程隔离、绑定技能、重复请求、证据、定时回调及只读会话。前端两套既有回归 89 项通过，Bot 模块及导航专项亦通过。隔离 Chrome 通过 8 项，外部请求与 JS 异常均为零。
- Native Doctor 所在的 service manager 套件在 macOS 系统临时根通过 361 项。第一次在工作树下执行的系统别名与端口子进程两项失败保留记录，改用系统临时根后均通过。能力准入扩展回归的两项失败在同一 HEAD 的未修改归档复现，涉及旧的 DataHub 拒绝原因断言，保留失败证据。
- 本轮运行 Project Constraints、文档治理、Python 索引、API Atlas、离线架构与协议验证。详细日志和验证回执位于工作树 `logs/`，原实施中断的本机记录仍可查。
- 以下是发布前本机验收记录。远端 CI、干净安装、部署、真实 DSH／数据源及定时运行验收均为 NOT_RUN。长期运行的历史增长及 64 MiB 维护索引边界尚未实测。冻结资讯之外的工具资料保留在原研究会话，结构化结果只验证冻结资讯的引用。
- 完整 API 套件初次单批超时，随后按原用例集合分批运行，219 项通过。离线 L4 回执标记外部门未运行，保留失败批次的原始日志和夹具。
