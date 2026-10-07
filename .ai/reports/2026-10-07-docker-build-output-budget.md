# Docker固定构建输出预算修补

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅固定Compose构建有界输出预算与既有stream脱敏，不新增组件或持久协议","diagrams":[]} -->

宿主macOS，功能修复；本地合同与适用Mac CI分开。base 40375ee803f324d6290830eb587a48173a0ab91c。
主任务真实构建66884bytes触发原64KiB guard；本次不执行真实build/network/install/service。

完整固定compose_prefix+build+research-web才使用BUILD_MAX_OUTPUT=2MiB每路（合计≤4MiB），
捕获与后验检查同预算，默认run_bounded/MAX_OUTPUT及metadata仍64KiB。非零不接受候选；
超限保留runtime_output_limit与精确owned进程树终止，无关进程不受影响。

公开构建启用既有stream。safe_log_text仅补传输URL脱敏：SOCKS、userinfo、loopback、
明确proxy行及畸形URL抑制，缘于构建错误可能回显宿主代理；保留错误文字和普通公开HTTPS
下载URL。原token/auth等整行省略及按行跨chunk缓冲保持，不扩provider/运行环境。

证据（logs/）：docker-build-budget-red.log 4真实FAIL；green 6PASS；negative 6PASS。
首次共享closure 1FAIL/373PASS：新增判定在availability前读compose_prefix，尚无installation ID。
修复通过前后缀短路避免非build读取该属性，仍完整argv精确比对；final closure 374PASS/27.90s。
覆盖真实Popen边界、>64KiB成功/非零尾部、伪build argv、>2MiB owned子树与无关进程、
共享minimal环境、公开setup代理、URL跨chunk及公有URL兼容。旧负例未删除。

source inventory已有docker_runtime和closest Python测试，无新增组件；Python索引核查而非虚构变更。
真实最终镜像/build/lifecycle、Mac GitHub CI均NOT_RUN，由主任务独立验收；其他平台交接。
独立Python review待主任务安排。停止旧容器自动重建权限pending，不实现。
无新依赖/软件源/TLS/全局配置/remote。ruff/black/isort/mypy环境不可用，不安装，不认证PASS。

最终门禁：JS104PASS；complete changed-set constraints无违规；documentation governance548文件
无违规；doc-sync与Python索引PASS；git diff --check PASS。planner记录validation_failure并
选L4，8本地门PASS。logs/docker-build-budget-receipt.json validator valid=true、BLOCKED，
4外部门NOT_RUN，mergeReady/releaseReady=false；绝非真实构建或整体发布批准。
