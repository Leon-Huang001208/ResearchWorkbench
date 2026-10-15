# Docker 周期报告数据投影最小修复

宿主macOS功能开发，Mac Docker Desktop验收。旧候选582e7fc4的三项CI全部PASS，
但真实Docker自动报告不完成；旧候选未合并，不能以CI替代运行验收。模型仍原scope
20calls/79894tokens/11501microUSD，上限20/100000/USD1，不增加或重置。

实际旧镜像a01fcdc7在受管stage只读根、相同产品Python、相同精简环境和同一真实冻结
宏观简报下，直接单次投影返回OSError errno30（EROFS）。原因是hot_documents导入
core.observability→core.settings→ensure_dirs，默认为镜像项目根创建旧目录。
该链还会选web-dev配置路径；报告数据投影不应初始化旧设置或读取开发.env。

修复仅将hot_documents日志改为既有report_documents一致的标准logging。Web已有日志
配置仍接收相同事件，独立子执行stderr归父适配器，Hot父事件进入原runtime.log。
不更改env白名单、镜像权限、报告内容、预算、数据库、模型或队列。
新隔离进程把core模块显式禁止，仍实际生成Word；旧实现会因导入旧facade失败。
9项Hot文档投影测试PASS；Docker旧实现真实失败保留，修复后整镜像须实跑验收。

此前诊断up时未建立PG relay，读取计划返回不可用而非items；该诊断失败保持，stage
最终受管停止。第二次诊断无需数据库或relay，只复现真实数据投影EROFS，并再次停止。
旧image、全部五卷、dev/g2b原容器及卷保留；未调用模型，未写入只读根或更改系统配置。

本修复作为单独有界的受管交付阶段继续，保留原r2三次修复计数及PR113，不重置旧记录。
原r2没有CI失败；发现的是本地Docker运行缺陷，旧源与已通过的CI不证明此新修复完成。
下一步合入完整Goal ancestry、验证当前集成、重建/运行/模式切换/最新恢复与MacCI，再合并。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"数据型Word投影移除旧设置日志facade的副作用，沿已有标准报告日志；不新增引擎、schema、队列或部署节点。","diagrams":[]} -->
