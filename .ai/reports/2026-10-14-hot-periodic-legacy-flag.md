# Hot周期管理与旧Automation开关解耦

macOS功能开发，hot-intel-continuation worktree，父候选5a32c302f。预算保持18calls/77375tokens/10464microUSD，上限20/100000/USD1。

真实镜像7a012ddf运行/Doctor健康，schema20 Hot正常；浏览器AI频道展示真实EmbeddingGemma2事件、规则重要性80/相关性95/热度0。点击周期简报显示Automation尚未启用。stage环境原有RESEARCH_AUTOMATIONS_ENABLED=0，三个Hot aliases错误调用旧service guard，组件测试默认旧Automation开启，故漏检。截图current-docker-plan-disabled-before.jpg保留。

修复删除三处旧service(request)调用，保留原Hot typed/query/body/user-action/controller授权；旧Automation全部guard不变。没有启动旧Store/scheduler、迁移、依赖或付费请求。路由仍委派HotWebService和原日志/错误传播。

RED日志hot-plan-legacy-disabled-red.log为1FAIL/3PASS；GREEN hot-plan-legacy-disabled-green.log为13PASS/1anyio弃用warning。扩大相关闭包hot-plan-legacy-disabled-python.log为66PASS，治理111PASS，项目约束/文档/文件索引PASS。覆盖关闭旧Automation的Hot读写、无动作403、不可用503、旧接口404及legacy.calls空。独立Python审查Approve。新镜像重建及该页面真实回归、当前MacCI尚NOT_RUN；旧5a32镜像证据不认证本修复。

<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"三个已有Hot管理aliases只移除错误的Legacy feature gate，仍委派现有HotWebService/PG/controller和唯一Hot调度器；旧Automation及Store、ResearchService/DSH节点、路由形状与权限不变，无新服务或第二调度。","diagrams":[]} -->

后续真实验证：b364d77cc镜像sha256:04260264…已构建，内存门因并发512MiB占用拒绝第一次up；保留失败回执，使用已授权dev暂停窗口重试通过并恢复原dev。真实浏览器在旧Automation=0时显示5计划、读取当前AI已冻结运行，截图current-docker-plans-fixed.jpg；未新建/启用计划、未模型调用。Docker导出按钮操作发生于计划停机后，不认证下载。Docker80停止后Native82接回同原PG并拒绝旧身份，最终暂停83；旧镜像与五卷保留。此证据scope是实际当前镜像Hot读/采集/管理与同库fence，运输仍acceptance-only relay，不认证外部TLS产品路径或Docker模型。当前MacCI仍NOT_RUN，Git绑定回执有效BLOCKED；完整Goal继续。
