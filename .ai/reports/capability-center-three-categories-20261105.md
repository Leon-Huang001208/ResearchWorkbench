# 能力中心三分类改造

- 任务：`capability-center-three-categories-20261105`。
- 宿主：macOS Mac mini；功能开发，本平台本地与适用同平台 CI 验收。
- 基线：`60416994f88eeead8a3891dbe9a7dfd617c566fc`，独立受管 worktree。
- 范围：技能、连接器、插件三分类；方法并入技能，工具进入关联详情；保留版本、权限、历史与旧链接。
- 非目标：新插件 SDK、第二执行器、生产数据迁移、部署或常驻服务更新。

## 实现

技能列表和选择器合并 Skill、通用 Workflow、历史 Method。原 method_ids、组合上限、版本和采用记录继续生效；内置方法复制为普通 Skill 草稿，走既有检查和发布，不改写原方法或冒充历史方法采用记录。

连接器复用 MCP 安装、DataHub 来源、本机集成和凭据管理。Tool 仅在相关详情/旧链接兼容区展示。插件继续使用原管理、受审权限与版本生命周期；不另建目录或安装器。定时任务薄入口复用原计划管理。

用户另明确要求解决每次重新安装 pytest：增加项目共享测试环境查找/准备脚本，按 Python、平台、锁定 Web 依赖和测试约束指纹复用。安装已单独获准，仅发生在独立环境；配置污染隔离、健康检查、锁冲突及失败保全有测试，原 .venv 和常驻服务不变。该环境为 project-shared，非任务退休资源。

## 验证与评审

- UI：13 套完整 JS 回归 171/171，零 skip，包含两个真实能力目录 fixture。
- 方法：9 项兼容/复制测试通过；保留先失败后修复日志。
- 环境：10 项测试通过，首次 prepare 成功，重复 prepare 返回 reused=true。
- 独立 Python 评审已解除 pip 环境外安装风险及健康覆盖缺口，批准当前修复。
- 独立 JS 评审发现搜索缺 label、MCP 刷新遗漏，均已修复并补先失败后通过的测试。
- 扩展能力兼容闭包：186 passed、2 failed、2 skipped（305.41秒）。两项失败在原始基线同样复现，异常文本一致，已保留 admission-baseline.log 和1760个Python源文件的Git blob核对证据；不归为本轮新增回归，也不标为通过。两项原生DSH源码验证因未指定 DSH_SOURCE_ROOT 保留 NOT_RUN。
- 项目L4本地验证114项通过；文档和完整changed-set结构门通过。
- 隔离浏览器run-4完整通过，10张截图；三分类、50项真实统一技能、主技能与历史方法共存、连接器搜索、工具详情、旧链接及定时任务入口均覆盖，pageErrors为空、model_prompts=0。Automation在fixture关闭，只认证入口与禁用呈现，不认证调度运行。失败run-1至3完整保留，4个fixture与浏览器均已退出。
- 两轮独立JS复核及Python复核均批准当前改动；最终候选SHA、远端CI和收尾尚待绑定。

证据目录：`/Users/leon/.codex/research/rwb-capability-center/2026-11-05/`；UI 原日志暂存任务 worktree 的 `logs/capability-center-ui-20261105/`，交付收尾前归档。

## 状态

未部署；未修改生产数据、秘密、模型配置或常驻服务。远端 PR、CI、合并与资源收尾须以实际回执补齐，当前不宣称完成。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "既有浏览器组件内重组目录和选择器，新增定时任务hash别名仅挂载原计划管理；不新增Host API、组件宿主、执行器或服务，部署与执行拓扑仍准确。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "定时任务入口仅调用既有计划列表和操作，不新增timer、任务类型、持久记录、执行流程或调度授权，原自动化图的节点和边不变。", "diagrams": []} -->

<!-- architecture-review {"group": "capabilities", "structure": "unchanged", "reason": "历史method复制复用原copy、草稿检查及发布链生成skill新记录；无新目录、存储、执行者或权限通道，原Host目录至唯一DSH投影拓扑仍准确。", "diagrams": []} -->

<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "在原Research Web Checks的两段pytest清单追加离线兼容测试，不新增job、runner、安装步骤、平台dispatch、工作流依赖或降低原门，现有验证图节点和连线准确。", "diagrams": []} -->

基线导出原 tar 返回元数据恢复错误，未隐藏失败；随后独立核对全部1760个Python源文件与基线Git blob一致才运行两项对照。对照只用于界定既有失败，不作为恢复归档成功认证。
