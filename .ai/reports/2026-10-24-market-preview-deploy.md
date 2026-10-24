# 全市场预览组合保全部署配置

宿主Mac mini / macOS；Web Native运维配置，不新增依赖、产品引擎、数据库或租户权限。

## 固定范围与真实授权

用户先明确选择纳入PR223组合保全部署，又明确允许加入随后合入的PR224。冻结PREVIOUS为当前实际常驻36fd990ceed88d2fc595443926105c4b2601fbf6、PAYLOAD为PR224实际合并e56d9718e12c2252128a6690ca202c7ae21f341e，包含组合表单幂等修复、DataHub财务现金流与代理/PIT修复，不自动纳入之后主线产品。

只新增reviewed-market-preview-v1 / apply-market-preview。旧profile、controller和evidence源码保持；reader193f4fcc、lock7c631d4f沿当前已部署身份。新mode完整接入严格业务索引、全部账号后台/工作流、市场采集空闲、原version4维护锁/BirthFence、会话模型/业务索引/档案保全及失败恢复。

## 本机验证

- RED：新增固定合同断言因原代码无mode而失败（1 FAIL/1941 deselected），保留red.log。
- GREEN：扩展原profile矩阵，完整test_model_provider_upgrade共2042 PASS，既有anyio弃用警告1条，124.99秒；operator.log留证。
- 只读使用已有ai-news测试包，并以PYTHONPATH固定当前源码；未安装Python包、未修改常驻环境或其他任务依赖。
- 独立Python审查已批准未提交二文件差异，独立101个新profile用例及ruff/black/mypy通过；最终SHA、完整本机Router和原三CI仍须再绑定。
- 原四文件操作员/网关/Native/多用户闭包共2304 PASS，193.38秒，仅既有anyio警告；ruff、black、isort、mypy通过。完整19文件本机约束、架构、文档治理和Python索引预检通过，日志均在本任务logs。
- 已核对requirements/web.in、requirements/web.lock、scripts/setup_web.py及原Bootstrap流程：没有依赖、入口或打包改动；安装说明补充新配置，最终同候选Mac安装仍是硬门。

## 文档和结构

同步安装/Docker、01/02/03/04/05、平台、资讯/周报、架构/开发映射/工作流、正式升级合同、预算及README复核。没有新节点或数据通道，既有图仍准确。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","diagrams":[],"reason":"仅在原Mac Native version4操作员增加封闭前版和获批产品身份，主实例/网关、维护锁、BirthFence、严格业务索引、全账号保全和恢复路径保持；没有新增服务、Docker权限、依赖或研究引擎，01/12图准确。"} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","diagrams":[],"reason":"新profile沿现有全账号后台/工作流和市场空闲门以及原租户根、维护栅栏和恢复事务，不新增HTTP或租户访问宿主能力，不处理新秘密或启用日程；资讯/周报与个人档案保全合同不变。"} -->

## 待完成

完整Router、最终独评、同候选三CI/macOS干净安装、实际部署/恢复artifact与双入口健康、当前用户根前后摘要及无临时覆盖的真实页面复验均待主任务执行。原PR223成功只认证产品，不能认证本配置或实际切换；Windows/Linux原生继续交接对应设备。
