# Mac mini 私网多用户容量

宿主macOS，功能开发；Windows/Linux产品验收交接NOT_RUN，不从Mac发产品dispatch。用户明确授权容量评估和合适并发上限调整，保留原会话/模型/活跃研究。

硬件实测Mac18,5，Apple M6，12核，25769803776字节（24GiB）。初始swap已使用2874.12MiB，压缩内存明显；memory_pressure -Q为50%。不能将历史swap等同当前内存耗尽，也不能把RSS当真实峰值。

在独立临时根以固定DSH和已有生产Python/Node启动真正Web/DSH pair：2套RSS约845MiB、40并发列表GET；3套6个子进程约1.06GiB、60并发列表GET（每用户20），请求全部200且空历史，3组耗时约0.030秒；全程swap2874.12MiB未增长，memory_pressure free percentage从49%至43%。关闭只属于临时池的进程并删除其临时根。无提示词、真实模型、管理员Keychain值或业务数据复制。

选择生产max_additional_instances=3，加保留primary为4总实例。每个额外用户暂按2GiB工作波动预算（假设，不是实测峰值），总额外预算6GiB，留出操作系统/桌面/Docker余量。不采用无限实例/自动驱逐，也不把轻量探测冒充真实研究压测。当前实例槽不等于账号数或单用户会话数，用户退出登录不释放槽位；管理员停止实例/停用才释放。

实现：RuntimePool允许显式1至4且默认2不变；常驻配置新增可选max_additional_instances，缺省1保持原部署，严格拒绝bool/非整数/越界；Doctor标准库只读报告配置容量和非法状态，不启动研究或读取模型凭据。源码池最大4与附接总数不同：若显式配置额外4，总数为5；本机只验收和选择额外3。

新增容量边界/复用/停止释放、配置类型和Doctor只读测试先红后绿。最终精确提交评审、CI、生产三账号并发/第四额外账号超限与既有用户不受影响、数据模型保全须独立完成，不因本地轻量探测标为已通过。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"复用既有逐用户Web/DSH池和管理员配置，改变有界容量而不增加部署组件、数据schema或执行引擎；旧默认保留。","diagrams":[]} -->
