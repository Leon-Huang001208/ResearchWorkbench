# 实际业务脚本与分析证据修复

宿主为24GB Mac mini/macOS；功能修复，本平台Native及安装验收。Windows/Linux原生保持NOT_RUN。

基线271c6cd的四用户真实任务均incomplete。FOMC记录22次工具错误，包括原文/分数利率断言、截短合同摘要、选择与映射不一致、观测ID误作citations、重复父来源及后续KeyError，最终预算耗尽缺报告。微软Summary结束行只有第一列为空而第二列有说明，列表来源也曾直接写入Excel失败。CPI需要前月/百分点事实，NIST上下文原文没有进入source_quote路径。原始批次FAIL及下载/隔离证据继续保留在私有操作记录，不覆盖旧结论。

先对失败类别添加离线回归：重复父来源去重、完整斜杠来源严格身份核对、统一四列表、选择器绑定选择和映射、原子Summary与独立说明表。前月CPI值来自实际表头，百分点用Decimal复算；前月同比只接受受支持的完整肯定发布上下文并核对本期表格。NIST原句进入既有观测路径，不认证中文推断或组织实施。脚本提示说明独立进程、实际返回文件路径，并按冻结要求选择治理指导。原research_quality.py、预算、缺口和用户合同不变。

独立评审发现CPI段落归属和Excel隐式精度损失两个问题：增加前后置否定/假设负例，关闭未识别上下文；工作簿重新读取后对照原始值或显式登记精度验收，失败保留旧文件。ExactValues仅保存底稿，不替代Summary正确性或Host质量判断。

本报告记录实现边界；实际执行的本地检查、精确CI、受控部署和新模型批次结果另由绑定回执保存。离线通过不证明22次模型工具错误已消失，也不证明所有分析已通过。原会话、模型配置、私网与DSH单引擎合同保持；无新依赖、凭据或迁移。新付费批次须取得针对具体版本的一次授权。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"原DSH报告资源与受限Host观测内修复格式和脚本指导，无新API或质量门变化","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"Summary和附表由原沙箱资源原子生成，不迁移用户文件或改变规范报告身份","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"仅修复冻结要求下的DSH提示，不增加调度节点权限或研究预算","diagrams":[]} -->
