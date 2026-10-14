# Hot周期管理与旧Automation开关解耦

macOS功能开发，hot-intel-continuation worktree，父候选5a32c302f。预算保持18calls/77375tokens/10464microUSD，上限20/100000/USD1。

真实镜像7a012ddf运行/Doctor健康，schema20 Hot正常；浏览器AI频道展示真实EmbeddingGemma2事件、规则重要性80/相关性95/热度0。点击周期简报显示Automation尚未启用。stage环境原有RESEARCH_AUTOMATIONS_ENABLED=0，三个Hot aliases错误调用旧service guard，组件测试默认旧Automation开启，故漏检。截图current-docker-plan-disabled-before.jpg保留。

修复删除三处旧service(request)调用，保留原Hot typed/query/body/user-action/controller授权；旧Automation全部guard不变。没有启动旧Store/scheduler、迁移、依赖或付费请求。路由仍委派HotWebService和原日志/错误传播。

RED日志hot-plan-legacy-disabled-red.log为1FAIL/3PASS；GREEN hot-plan-legacy-disabled-green.log为13PASS/1anyio弃用warning。扩大相关闭包hot-plan-legacy-disabled-python.log为66PASS，治理111PASS，项目约束/文档/文件索引PASS。覆盖关闭旧Automation的Hot读写、无动作403、不可用503、旧接口404及legacy.calls空。独立Python审查Approve。新镜像重建及该页面真实回归、当前MacCI尚NOT_RUN；旧5a32镜像证据不认证本修复。

<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"三个已有Hot管理aliases只移除错误的Legacy feature gate，仍委派现有HotWebService/PG/controller和唯一Hot调度器；旧Automation及Store、ResearchService/DSH节点、路由形状与权限不变，无新服务或第二调度。","diagrams":[]} -->
