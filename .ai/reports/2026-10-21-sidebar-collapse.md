# 左侧会话栏收起修复

任务 `sidebar-collapse-20261021`；宿主 macOS，任务为 Web 功能修复；不属于桌面端交付，不部署常驻服务，不调用真实模型。基线 `db8baf07c04e59fff34446d091b225f1e2894981`，独立受管 worktree 实现。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"沿用共用shell、原生DOM事件及模式导航状态；仅将桌面展开控件移至既有topbar绝对定位，并修复搜索文字与可见焦点恢复，不新增页面、公开API、数据契约或框架执行节点。","diagrams":[]} -->

## 原因与改动

- 原实现收起后改用窄主导航内按钮，CSS另为搜索加40px上间距并隐藏其span。现改为topbar内独立桌面展开按钮，与会话栏标题操作区同高，不增加空header高度。
- 保留搜索文字与导航项坐标；移动端保留menu-toggle与抽屉关闭。已有data-toggle-sidebar/data-collapse-sidebar、模式独立保存及日志/错误处理流程继续复用。
- 点击切换后焦点落在可见按钮。跨1050px断点时，恢复响应式隐藏导致的失焦；主动离开仍可见控件后不抢焦点。既有research_navigation_viewport_changed日志保留。

## 验证证据

- 编辑前：新增导航与焦点回归在原实现失败，记录 `logs/sidebar-red.log`。初始目标79项测试指出一项旧预期仍要求主导航按钮，按新的顶部入口更新。
- 完整UI回归：`node --test --test-reporter=tap tests/javascript/research_web*.test.mjs`，最终输出见 `logs/sidebar-ui-full.log`；717 PASS、2 SKIPPED、0 FAIL（后续焦点补测按最终日志复核）。
- Router本地闭包：文档治理、Python索引只读检查、Research Web架构/UI、Project Constraints及完整文档/Actions/跨平台源码合同；结果记录 `logs/sidebar-plan.json`、`logs/sidebar-constraints.log`、`logs/sidebar-doc-check.log`、`logs/sidebar-py-index.log`、`logs/sidebar-router-tests.log`。
- 真实本机Chrome：`node logs/sidebar-browser.mjs` 使用完整产品app.mjs及真实CSS、隔离HTTP假数据，覆盖FinGPT/Claw、light/dark、1440/1051/1050/390宽度、三次切换、刷新恢复、搜索开关/输入、可见焦点及断点。截图与完整脚本/日志存于logs，正式入口收尾时归档；假数据不证明后端或模型调用。
- 独立评审发现focusin-only标记在主动失焦后可能抢焦点，已增加可见控件focusout清除与对应单元/浏览器回归。最终候选还须独立复核。

## 安装与交付边界

无Python/Node依赖、固定DSH、安装器或配置变化；requirements/web.in、requirements/web.lock、scripts/setup_web.py、安装文档与Bootstrap工作流已核对，按原合同保留。必需Project Constraints、Research Web Checks和同候选macos-14干净安装CI在发布后取证，尚未运行时保持NOT_RUN，不能由本地成功替代。Windows/Linux产品任务不在Mac dispatch；本次不改变其支持状态。README描述的顶部折叠仍成立，复核回执已更新。

合并与资源收尾只通过受管Git入口；只回收本任务资源，保护主工作区未跟踪文件、其他任务worktree和服务。常驻服务版本未更新。
