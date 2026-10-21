# 资产观察部署 CI 大日志超时修正

macOS/Mac mini Web部署修正；用户已明确授权部署资产观察。PR172合并d7538504，通过同候选三CI及独立评审，但停机前资格复核两次因2.31MB Checks日志下载超30秒拒绝。单独真实只读下载分别47.06/49.07秒，HTTP/1选择未缩短；仍为原c688服务且无主/网关journal。未调用模型或供应商。

仅CI日志调用预算改120秒，普通命令30秒、8MB输出上限、最新主线/合并评审/三CI/实际checkout树及Mac标签证明原样保留。资产专项固定读取器完整SHA256，必须存在、普通100644且逐字节一致；不扩大为任意工具路径。冻结恢复包纳入同一已审读取器，旧不可变controller和自动白名单不改。

定点先复现默认30秒不满足新日志预算的红灯，后测试日志120、普通命令30、超时拒绝、错误树拒绝、证据文件变更/模式/删除拒绝。真实部署与浏览器仍待修正候选独立评审、Router和同候选CI后执行。安装无依赖变动，requirements/web.in、web.lock、setup_web.py和原Mac Bootstrap由同候选安装验收证明；其他平台原生NOT_RUN。

两个直接相关Python模块本机226 PASS/5.25秒，日志logs/timeout-green.log。初次接入Git对象读取使用了完整路径，正例发现helper会自动加模块目录；改为固定evidence.py文件名后，正例及所有内容/模式/缺失负例通过，未放宽校验。同候选综合CI和Mac安装尚待完成。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"只修正既有资格读取器的有界日志下载预算并固定工具摘要，不改变主实例网关或DSH节点与恢复拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原空闲、请求冻结、账号隔离及完整业务索引和会话保全不变，未修改业务根或凭据。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原三CI与完整实际树证明保留，仅本机日志下载有界等待变更，无新job/runner/依赖或平台产品派发。","diagrams":[]} -->
