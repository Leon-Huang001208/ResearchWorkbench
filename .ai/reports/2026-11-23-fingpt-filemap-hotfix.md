# FinGPT 文件索引与回滚修复

承接原 PR #328 / rwb-fingpt-weknora-replacement-20261123，不新建 Native 任务或重置其计数。

正式部署在首条文件索引读取处报错：实际 Store 保存路径字符串，旧测试错误地手造对象值。没有删除数据；原before、版本与原件经核对一致后，仅收窄失败事务未执行的删除意图，再经原已审executor完整BACKWARD恢复7dc，结果rolled_back/preserved=true。用户最终删除授权不变，新候选继续执行。

现直接按Store实际格式处理，回归通过真实Store.files()登记文件；正式报告保留而专有附件删除。首次删除限定forward阶段，rollback不开始未执行的删除。6项相关回归通过，不重复既有后端/模型/旧广域测试。Mac功能修复，其他平台原生NOT_RUN。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"仅将聊天退役读取修正为原Store真实字符串索引格式，原用户数据目录、身份权限与DataHub/正式报告保全边界不变，不新增服务或存储。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"只限制原联合升级回滚不首次调用删除，继续原锁、检查点、源码资格和完整恢复顺序；无新执行器、后台作业、部署节点或恢复框架。","diagrams":[]} -->
Product-Progress: not-required — 本次仅修正已登记工作台切换的存量文件索引和回滚动作边界，不增加用户能力或导航。
