# 实际业务报告证据与验收误报修复

宿主：macOS Mac mini；功能修复，Native平台验收；Windows/Linux NOT_RUN。

输入证据：私有四用户官方资料桌面研究的独立审查，发现错误融资对账、CPI口径/单位、SRF方向、来源ID、claim操作数/期间和r4笔记血缘问题；同时发现独立工作簿验收器把合理舍入及尾列空值误拒。原四报告incomplete及原FAIL保留，不修改旧会话、报告或模型配置。

修复：报告资源新增纯格式/算术预检查helper与独立Summary验收器；DSH提示明确使用真实来源ID、核查表头与资金方向、全部有符号子项对账、不伪造期间/单位或计数。Host质量算法、可信观测来源、一次补查预算与409规则不变。不存在新引擎、依赖、HTTP端点、数据库或迁移。

复现与本地检查：先新增6项故障类别回归，确认原版本缺少工具（6失败）；实现后6通过。原Host可核验claim仍通过，替换真实观测内容后保持拒绝。完整目标检查、独立评审、CI、部署及真实四用户复验结果将在任务私有证据及最终交付回执记录；本文不提前宣称通过。

安装核对：仅现有Python标准库，requirements/web.in、requirements/web.lock、setup_web.py及安装工作流无须依赖变更；同候选macOS干净Bootstrap证明安装兼容。无密钥进入代码/报告/CI，临时模型授权只用于系统钥匙串测试账号，结束撤销并恢复3槽。

边界：这些helper不生成Host观测、不证明语义真伪、不能使无法表达的表格或翻译自动通过。真实付费复验仍是独立验收，失败保持incomplete/invalid，不把预检查、下载或模型自评当passed。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"只在现有报告resources和DSH提示补来源算术引用预检查，不新增端点进程或可信事实层，Host质量合同保持","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service提示修改不改变Automation准入调度授权与恢复，唯一DSH执行循环及已有工具预算保持","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"报告helper及独立工作簿验收修复复用原文件与交付边界，不迁移旧数据或重写现有模型配置","diagrams":[]} -->
