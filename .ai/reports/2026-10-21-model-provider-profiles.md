# 模型服务商多连接实现

- 任务：model-provider-profiles-20261021；宿主 macOS Mac mini，Web 功能开发。
- 隔离目录：本任务 feature worktree。主工作区、真实凭据、会话和常驻服务均未更改。
- 目标：按确认v0提供卡片/图标/完整添加页，独立命名profile凭据，保全legacy账号/旧会话/旧日程。
- 不新增依赖，不改固定DSH协议，不执行真实模型，不部署。

## 验证状态

交付进行中；首轮凭据隔离/密文56项通过，profile专属回归仍在逐项完善，最终检查与CI状态以任务最终回执为准。原型通过不视为正式产品已验收。正式UI组件的隔离示意预览在本机回环端口，不连接常驻服务。

第一次profile凭据回归RED已证实两个固定ref无法隔离新账号；修复为严格注册profile映射且不搬旧Key。独立评审发现历史子研究inactive、未知回执、日程锁外竞态和引用后归档问题，均补充定点反例并修复。

初次大范围API在较早未完成源码运行：222通过、两项失败（任务模型字段后续已修复；Word原生环境问题已通过回到本机产品解释器、复用既有dev工具后原生验证通过），不将其标为最终候选通过。所有必要平台门保留，Windows/Linux产品交接NOT_RUN，不从本机触发。

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "独立账号仍在已有系统/实例加密凭据后端内，旧namespace与密文格式保留，新profile envelope只扩展账户绑定；Native/Docker拓扑和安装入口不变。", "diagrams": []} -->

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "已确认v0的供应商卡片和完整添加页在原settings路由挂载独立DOM组件，复用主题/控制器/API；不引入框架或新执行通道。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "原Host新增命名连接CRUD与激活路由，端点清单和API Atlas已重建；执行仍走原DSH/Store/凭据桥，不新增研究引擎。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "研究日程仅增加原Store行内的profile身份并在原create服务锁内复核；已有定义SHA、批准、调度及执行拓扑保持，旧任务保持legacy绑定。", "diagrams": []} -->

<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "两个DSH逻辑ref保持，受管Python桥由原Store注册项选择独立物理账号；会话profile绑定属于原Host生命周期元数据，不改变固定DSH协议或agent循环。", "diagrams": []} -->

<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "新增离线profile回归进入原Checks步骤与原JS通配符，预算记录现有五run和60秒增量；Mac Bootstrap沿原入口，不新建job或触发他平台产品CI。", "diagrams": []} -->

<!-- architecture-review {"group": "private-multiuser", "structure": "unchanged", "reason": "新连接接口继续通过原用户网关和tenant后端隔离；服务器官方上游限制覆盖新保存/激活路径，不新增任意端点访问或共享凭据命名域。", "diagrams": []} -->

## 本地结果（feature 工作区）

- 完整 API：202 passed，930.09 秒；使用本机产品解释器，并仅通过任务命令 PYTHONPATH 复用已有 dev 工具，未安装依赖。
- Router 相关 Python 闭包：739 passed / 4 skipped，82.89 秒。
- 专项模型 profile：16 passed，159.72 秒；旧账号不搬迁、独立账号、首次无Key兼容连接、未知提交、回滚、闲时/子活动、引用删除、日程竞争与兼容Key代次均覆盖。
- Node 24.19 完整相关闭包：867 passed / 2 skipped；此前两个旧表单位置断言迁移到新组件真实功能，保留本机模型目录展开。
- Ruff、Black、isort、两个新增 Python 模块的相关 mypy 已执行通过。后续仅涉及刷新按钮位置/折叠焦点的 UI 改动，再跑定点17项全部通过。最终集成候选重新绑定所需验证。
- 浏览器：正式组件及完整Web/Host夹具、空搜索Enter、同协议返回草稿、保存/焦点、窄屏明暗、刷新折叠/焦点；Chrome CDP真实composition状态下Enter不选择，结束组合后正常选择。IAB不支持该IME命令，因此换独立Chrome测试，测试标签已关闭。所有模型请求为0，生产数据与钥匙串未访问。
- 用户后续确认：顶部仅添加服务商；手动刷新在运行时信息内。
- SDK缓存审查绑定固定DSH 7ecf564：DeepSeek/搜索每次操作重新resolve，无跨请求Key缓存；兼容prepare捕获Key，当前协议route替换Key时更新global connection_revision（即使该协议不是全局默认）。
- 明确边界：研究任务日程research_task锁provider/model/profile；Skill/Workflow/Report Workflow保留原有执行时默认模型语义，不补造历史审批。常驻部署、真实供应商及跨平台实机未执行。

PR #165 首轮通用 CI 为 1052 passed / 11 skipped / 12 setup errors；新增 profile 夹具漏隔离 Host 签名与 DataHub 元数据凭据，CI 无系统钥匙串而正确失败关闭。以系统 keyring 操作抛出受控异常复现同一初始化失败，再复用原 API 测试的进程内凭据隔离模式，保持全部产品保护规则及断言。该修补只改测试与本报告，产品源码未变；最终候选另绑修补测试、通用检查及 macOS CI，旧源码验证若复用须保留原候选和字节一致性证据。

证据校正：此前“钥匙串未访问”不能覆盖遗漏隔离的 Host 初始化路径；模型凭据由内存夹具处理，但 Host 签名与 DataHub 元数据在旧夹具中可能经过系统后端。修补后所有该模块的系统 keyring 操作均绑定独立内存后端，预览夹具也同步隔离；不宣称旧运行具有完整的系统凭据隔离。
