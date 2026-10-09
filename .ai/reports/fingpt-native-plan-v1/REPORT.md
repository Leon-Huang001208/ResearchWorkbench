# 原生研究计划本地交接

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在现有研究空间活动标签内追加来自原生快照的计划，只增加既有views/shell渲染与组件样式；没有新导航、控制器、数据源或模块节点，原架构图仍描述同一依赖边界。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有projection恢复DSH日志并新增只读plan字段，由service原有展开表达式自动带入详情与SSE；不修改service流程，不新增路由、正文库、持久schema或执行引擎，原模块图保持有效。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"固定DSH中已有Todo模块以原preset装配及tools/sessionProjections注册，guard只新增精确工具名并保留预算与归属；不改变部署节点、固定pin、依赖、进程生命周期或新建调度器，原运行时图仍适用。","diagrams":[]} -->

## 状态
本地实现与聚焦验证已执行；补充真实浏览器渲染原生日志投影的6项检查。完整验收尚未完成，
Mac CI、完整产品浏览器研究流程、干净安装、模型live分别未执行。
固定基线、逐项命令与RED/GREEN见 PROGRESS.md；剩余门见 BLOCKED.md。
最终聚焦Python180通过/0skip，Node24 JS69通过/0skip/0todo；固定原生插件集成与真实落盘日志
恢复通过，L4的9个本地gate全部PASS。机器回执valid=true但result=BLOCKED；不是已上线。

## 行为
全量原生Todo快照、原生回合/seq写入版本，无稳定item身份。新回合清空，日志缺口后的回合
不推断；坏记录/冲突重复隐藏计划并提示，历史不足明确告知。取消/失败保留任务终态，Todo状态
不扩充blocked。研究空间显示转义正文，与既有Workflow说明和文件交付判定分别保留。

## 授权与安装核对
用户本轮明确允许补齐门禁所需文档、Python索引及API Atlas生成页；没有放开产品源码、依赖、
CI/策略或发布。`requirements/web.in`/`web.lock`、`scripts/setup_web.py`、安装文档与bootstrap
workflow只读核对：使用标准库及已有项目日志/既有固定DSH模块，不新增包；setup读取研究preset，
已有固定Web profile包可加载Todo。当前pin相对任务书观察值已由上游变为48504f07，未在本任务改动。
上述文件字节未修改；干净安装和Mac CI未执行，兼容性保留待验，不以已有环境作安装证明。

## 集成边界
native-integration.mjs在真实独立Node进程中使用测试dataHome/DSH_HOME/JSONL根和真实AgentLoop、
tools、sessionProjections、Loader与guard；不监听端口，不重启/改写生产runtime。真实工具执行两次，
原生JSONL写入与耐久读取、下一回合清空已验证；真实事件被Python投影恢复。模型调用0。
测试以实际preset的Todo段验证Loader装配；Python装配测试另验证完整research preset展开。
这证明固定插件集成，完整HTTP服务/模型驱动研究仍NOT_RUN。

## 其他平台
Mac不发送Windows/Linux dispatch。额外本地集成catalog既有Windows原生用例保留跳过，
对应Windows真机/CI未验证；不以macOS模拟合同替代其原生证据。

## 浏览器视觉证据
browser-receipt.json及四张PNG取自实际本机浏览器。已验证原生日志中的两项进行中、
完成清单/刷新同一版本、真实下一回合清空；另验证明确标注的坏事件/长文本协议样例。
390px宽只读预览调用当前views renderer与styles，HTML保持转义、无横向溢出。
测试服务仅允许GET固定资源，已停用；不冒称完整产品服务、模型或浏览器研究live。
