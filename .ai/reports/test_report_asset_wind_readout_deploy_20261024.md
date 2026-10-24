# 资产幅字段固定 Native 部署准备

本任务沿用户既有常驻部署授权，为PR216“幅”字段产品建立封闭资产V8。PREVIOUS固定已核实的实际驻留b4384470；源码与测试的PAYLOAD现固定组合merge `08406f018a76f2ebb67d8478c97486ca4ef18d76`（包含PR216幅字段与PR217数据源），两项产品原三CI各自通过，操作员组合重新验收；预备c4c58候选验证与最终配置/实际部署分开取证，不把预备candidate当正式产品。

复用version4维护锁、BirthFence、严格controller/evidence、64MiB业务读取和全账号/档案/模型/会话保全/恢复；V8追加到原真实Git范围、错前版、市场inflight、恢复与出生围栏矩阵。V8继承Discovery后台空闲检查，跟踪/Automation/Workflow活动或异常在进程/HTTP探测前拒绝，旧模式身份与分支保持。

RED先观察缺少ASSET_V8_MODE的合同失败；此前两次环境尝试分别缺pytest及误加载旧SQLAlchemy conftest，未冒称缺陷复现。使用已批准的既有测试依赖目录及与CI相同的confcutdir后，RED明确为缺少profile。预备实现1712项111.77秒通过；独立定点111项及Ruff/Black/mypy通过。最终pin、组合回归、真实Git、完整Router/CI、部署保全、认证实页及收尾仍各自留证，不认证未执行层。不安装新包、不启用数据库或日程、不改外盘、不运行模型。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在原Native操作员添加固定V8身份与CLI分派，主实例/网关/DSH、version4维护和保全恢复拓扑保持，无新运行节点或数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"V8复用全账号索引与档案保全、64MiB读取和BirthFence，继承已上线Discovery后台活动拒绝；不新增账号、权限或数据根，原私网图准确。","diagrams":[]} -->

主线在切换前合入PR217，因此未执行旧bbf候选；其原三CI和本机1943项通过证据已单独归档，不能认证新组合。新基线无锁依赖或数据库DDL变更，本任务不启用研究仓；最终固定08406、重审真实Git union并重新执行本机/三CI/Mac安装。
