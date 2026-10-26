# 导航常驻交付的精确产品范围

macOS Native；用户明确授权部署导航并保留现有会话及模型配置。实际primary/gateway仍为5df8e17e，原联合操作员仅允许0d73c034产品blob，已合并PR168的五个导航文件被真实只读资格检查拒绝（model_upgrade_payload_changed）；服务未切换。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在原模型服务商联合操作员内增加五个已审UI文件的固定Git身份，其他产品仍绑定0d73c034。旧控制器、v4冻结/恢复、wheel、Native和网关部署节点、DSH及数据根均未改变。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原空闲证明、BirthFence、全请求冻结、保全摘要和联合回滚步骤不变；五UI文件的精确blob与模式校验进入同一冻结恢复包，不新增权限、账号API、数据结构或任意UI放行范围。","diagrams":[]} -->

## 实现与验证

原模型基线PAYLOAD保留0d73c034；仅app/core/intel/shell/workbench五个UI文件使用PR168合并SHA4e8be6ac的blob和Git模式，目标须包含该祖先。其余后端、依赖及未知UI仍保持原逐字节规则，工作流只允许原测试插入。没有修改自动resident兼容白名单、旧controller.pyz、v4事务或恢复流程。

新增正反例先在旧实现复现1失败/6通过；新增范围后原完整模块106项通过（0.72秒，1项既有Starlette弃用警告）。代码和测试使用原日志/异常设施；正式交付继续完成Router、独立评审、原通用CI和同候选Mac安装。未安装依赖、未调用模型。

独立评审发现旧差异遍历会漏掉回退至PREVIOUS而从diff消失的必需UI；新增单文件/全部回退两例先复现失败，改为差异与五文件并集后完整模块108项通过（0.61秒）。评审另独立跑9个范围正反例通过，高风险项关闭。原275项升级/网关/多用户组合、112项治理已通过；Ruff/Black/isort、该模块mypy、文档同步及索引检查通过。后续合格候选及实际部署证据单列，不回写成早期快照已部署。

最终操作员与原网关/多用户组合复验277项通过（23.24秒），部署状态仍待远端与现场门完成。

只读部署预检得到primary63会话/3193文件、12个私有用户合计44会话/3288文件；仅保存摘要和模型配置指纹，不输出正文或Key。这是预检快照，实际保全仍由切换锁内的独立摘要与部署后检查证明。后续活动或未知保持deferred，不强停研究。

真实部署和浏览器效果尚待合格候选；本报告不把源码/离线/安装证据当作已部署。最终Git交付与实际升级回执保存在各自受管证据目录。Windows/Linux产品原生NOT_RUN，资讯worker、数据库和其他任务资源不属于本任务操作范围。
