# 今日发现原生双栏：封闭Native部署配置

宿主Mac mini/macOS，Web Native运维任务。用户已明确授权常驻部署和真实页面只读验收，并授权协调周报/全市场统一窗口；禁止真实模型和生产跟踪。本配置只新增固定v2身份，旧profile、不可变controller及严格evidence字节保持。

前版实际36fd990c，批准产品PR226 merge01fa32c8；现存周报0ddde75a251543d2b0943fdf980972b6为needs_attention，background_idle=False，尚未运行apply。其维护由既有授权任务正式交付，不能手工改catalog/取消Native/重发旧模型。最终目标若推进，重新固定并验证完整候选，不扩宽为任意业务代码。

实现扩展原ASSET_PROFILES、CLI、精确产品/reader/锁、完整保全和恢复矩阵；新恢复mode强制manifest.source绑定，旧mode兼容不变。首个红测缺mode失败；原矩阵新增mode后21处fixture映射/预期缺注册，旧2115项通过，原失败留logs；现已补齐真实Git/source丢失反例/CLI/市场未知列表并复跑。未安装任何依赖或修改生产。

最终Router、独评、原三CI/同候选Mac安装、真实空闲与保全、认证页面截图及收尾分别取证。

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "diagrams": [], "reason": "仅在原Mac Native version4操作员增加封闭前版/产品身份，主实例/私网网关、维护锁、BirthFence、严格业务索引及全账号保全/恢复边界不变；新source绑定是现有恢复合同的模式内校验，无新HTTP、服务、数据库、引擎或权限节点，原01/12部署图准确。"} -->

<!-- architecture-review {"group": "private-multiuser", "structure": "unchanged", "diagrams": [], "reason": "仅在原Mac Native version4操作员增加封闭前版/产品身份，主实例/私网网关、维护锁、BirthFence、严格业务索引及全账号保全/恢复边界不变；新source绑定是现有恢复合同的模式内校验，无新HTTP、服务、数据库、引擎或权限节点，原01/12部署图准确。"} -->

本机配置验证：完整operator 2151 PASS/123.45秒，原操作员/网关/Native/多用户四文件闭包2413 PASS/142.70秒；独评109个v2用例PASS、代码批准进入候选CI。Ruff/Black/Isort/Mypy、完整changed-set项目约束、架构/文档治理、113个JS治理测试与Python索引已通过。部署资格尚未取得，不把这些离线结果标为实际切换或页面验收。
