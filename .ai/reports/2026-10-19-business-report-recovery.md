# 真实业务报告恢复

宿主macOS Mac mini；功能修复，仅本平台Native/安装验收，Windows/Linux原生交接NOT_RUN。

上轮440f8fb2b已正常合并部署，四用户真实DeepSeek任务同时运行，结果四份incomplete：FOMC重复错误操作数耗尽工具预算无规定报告；NIST带准确ID/标题/定位的来源单元格被独立oracle误拒，离线修复该误报后仍发现control_id以C01等本地编号替代官方标识，原严格覆盖检查继续拒绝；其他中文解释仍未核验。原FAIL保留，不能说付费验收已过。临时4密钥清除、账号停用、槽位恢复3；原60会话2964文件和模型设置保全。

修复：_evidence_decimal接受有限有界Decimal，claim所有操作数转精确JSON字符串；source_references只按实际ID及准确Host标题识别明确定位，不从定位猜身份。prepare_contract在原resources路径写有界实际证据投影，SDK按task/合同读取，减少手抄长JSON与重复试错。模型仍须读源/做底稿/正常检查；quality_result不读取此副本，伪造副本、scope和链接负例保持拒绝，原research_quality.py/补查预算/missing不变。

新增故障回归先red后green；原macOS沙箱实测直接读取投影和Decimal工具，脚本506字节、零模型调用。独立审查发现Decimal操作数未JSON化的P2，修正并保留反例。源码检查、CI和部署证据另归档，不提前宣称新真实模型通过。上一轮一次付费授权已消耗；下一次四用户付费复验须对具体固定版本另获授权。未引入依赖、端点、数据库迁移或凭据写入。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"仅沿既有冻结合同与资源文件提供有界只读派生，Host评分仍独立读取原输入，无新API或执行节点","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"在现有会话resources内增加可再生派生JSON格式，不迁移历史或用户设置，文件格式已同步模块文档","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"DSH提示与报告资源恢复不改变Automation准入授权调度和恢复，无新增模型回合或补查预算","diagrams":[]} -->
