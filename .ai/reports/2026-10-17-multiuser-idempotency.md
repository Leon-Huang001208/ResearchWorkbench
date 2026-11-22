# 私网研究提交幂等头修复

宿主 macOS Mac mini；功能缺陷修复；验收范围为本机 Native 与策略选择的 CI，Windows/Linux 产品验收 NOT_RUN。

四账号压测在模型受理前发现网关白名单剥离 Idempotency-Key；原 Web 访问日志有测试会话 /messages 422，四会话未进入 running。不可把本次当作真实模型容量通过，也不根据 idle 单独宣称零模型调用。

增加单个幂等头透传；Cookie、Authorization 和伪造租户 key 继续剥除/由服务端替换，不记录头值。缺失幂等头继续由后端拒绝。无依赖/schema/模型配置变更。requirements/web.in、web.lock、setup_web.py 与 Bootstrap 无需改动；安装兼容性仍以策略与 CI 证据为准。

回归先红：--confcutdir=tests/research_web pytest 定点结果 2 failed/1 passed，两个大小写请求头均观察422而非202。默认根conftest需未安装SQLAlchemy；使用既有Research Web独立合同入口，无新依赖。

后续验证与交付证据待实际执行追加。

实际本地验证：117项Python多用户合同通过；112项L4 JavaScript合同通过；Ruff/Black/isort与Python文件索引通过。项目结构约束初次要求补齐private-multiuser关联文档和README复核，按原门补齐，不能以初次失败冒充通过。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"在既有认证网关到逐用户Web路径只补必需幂等请求头，不新增部署节点、认证来源、存储schema或执行引擎；浏览器凭据仍不转发。","diagrams":[]} -->
