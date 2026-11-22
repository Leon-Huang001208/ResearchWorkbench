# 本地知识库 Native 联合升级与主动回滚

本任务由用户明确批准知识库执行计划及受管更新；后续明确由用户本人注册真实邮箱账号，并要求 WeKnora 通过 Tailscale 私网供获准设备访问。宿主 macOS，任务为功能开发，产品 Windows/Linux 原生验收独立交接。

## 固定产品与不变设置

新增 `reviewed-local-knowledge-v1` / `apply-local-knowledge`，固定前版 `33b3044dd68197106c5018e31482762cb1e02ea1`。产品提交以最终 `LOCAL_KNOWLEDGE_PAYLOAD` 字面量为准，必须为工具候选祖先；产品之外仅允许操作员、原测试与列明文档和生成源码链接文件变动。唯一安装例外为 `scripts/setup_web.py` 的固定两个 blob，模式严格 `100755`，真实 Git 树已核对；其他五项安装合同继续完全相同。

原 v4 事务、三把锁、BirthFence、全部业务索引、账号原件、模型配置、原 MCP 位及原执行器沿原门检查，不借用 `apply-fingpt`。新模式只持久绑定知识库 origin。新起进程、私网和本地健康分别验证；QA 反转负例曾真实失败，增加验证后进入受管回滚。

## 主动回滚

使用本模式独立胶囊、accepted seal 与 `rollback-local-knowledge --rollback-target`，不冒用 FinGPT 标记。先保全回滚开始时的最新用户状态，再回原源码、wheel、安装清单及网关 origin。原 origin 字段不存在时恢复缺失，不制造默认旧值。完成清理中断可接续；错误 target、胶囊篡改、忙状态均拒绝。普通 recover 只恢复未完成事务。

## 真实阶段与证据

- 原 WeKnora 标准实例已复用，冷备份和隔离 Postgres 恢复读回通过。
- 原生本地 BGE-M3 实际 1024 维；私网 HTTPS 9443 页面 200，匿名知识库 API 401，模型路径 404；现有 443/8443 路由保持。
- 四份原公开样本及问题数组精确复用，20题19命中、160引用全部原件/分块核验、scope违规0、生成请求0。该结果属于独立 bootstrap 验收身份，不代表正式用户已绑定或研究报告质量通过。
- 用户本人账号已注册。临时测试的 RWB 绑定和同步状态已逐文件校验归档，公开源文件保留，owner 标记退出；不会由新身份继承测试知识库或秘密。
- WIP Native 39项曾通过；独立评审另发现 setup executable mode 例外误写为644，真实755 accepted/644 both负例均先失败后修复。最终 exact-SHA、CI、正式安装、登录后研究与另一设备验证以最终回执为准。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"新增固定知识库升级profile仍复用原Native联合事务和双入口启动，不新建研究引擎或状态机。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"网关仅从受管配置读取固定资料origin，既有账号、RuntimePool、MCP与原件保全角色保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"新模式与主动回滚反例沿原Native测试模块及原三CI运行，平台门、runner和发布准入不变。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在既有安装清单和网关配置持久绑定资料origin，仍沿原Native与Docker分工、账号Host和固定运行时启动链，不新增业务执行器或跨平台支持声明。","diagrams":[]} -->
