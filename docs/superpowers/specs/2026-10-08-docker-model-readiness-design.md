# Docker 模型凭据与文本研究闭环设计

用户于2026-10-08确认最小设计并要求继续实施。任务 docker-text-research-20261008-a1；macOS功能开发，基线 b352ffa304c0b17c3260ed9417f083aac0fedf64。继承旧双运行时成果，不重做旧任务、c1关联或通用框架。

## 受控模型后端

Native仍使用直接选择的macOS系统Keychain，固定ref为RESEARCH_DSH_API_KEY，无文件/环境回退。仅由受管Docker启动器选择docker-private-file；后端、固定私有根及稳定安装ID通过非秘密绑定传给owned overlay与私有Python桥接。浏览器和研究消息只能使用resolve/describe/set/unset，不接受路径、后端或其他ref。

模型文件在既有凭据挂载内的独立模型叶 `/run/rwb-secrets/private/models/<installation-id>`，不读取DataHub记录或命名空间、不使用container ID或固定data路径散列。复用credential_backend.py的pin/no-follow/私有权限/单链接/有界读取/锁原语，模型事务保存在模型专用模块；不改变原DataHub后端默认行为。

每次操作确认目录与锁inode。读取仅接受规范化私有记录。写入在持锁范围读旧记录、写0600临时文件、fsync、核对临时及旧inode、原子replace、fsync目录、核对落盘；replace前失败只删除本次临时inode，旧值不动；replace已调用而结果或后验不确定，不删除已发布记录、不声称已回滚，只返回稳定不确定错误。删除亦须确认旧记录后unlink并fsync；提交后异常不假报未删除。相同安装重启/重建可读，不同安装隔离，Native/Docker不迁移Key。

文件权限不是加密保险库，不能防容器内同UID任意代码或Docker管理者。不得挂宿主Keychain、HOME或Docker socket。秘密不进入argv、环境、镜像、Compose、摘要、日志、公开API或浏览器存储；resolve仅经必要私有进程管道传递。

## 跨语言与产品状态

Python/JS使用受控来源system-keychain和docker-private-file，JS校验来源与受管启动器绑定一致。保留Host浏览器认证record平面。设置页/Service/Doctor使用原有状态和错误体系：Key留空保留、新Key替换、独立清除；活动父/子研究拒绝改Key，提交结果不确定沿用model_configuration_uncertain拒绝研究。未配置Key/后端故障不能阻塞设置页和核心健康。

## 文本研究、回归与浏览器

先用已有测试替身覆盖设置→桥接→研究→保存→恢复的应用行为以及缺凭据、不可用、鉴权/网络失败、取消、重复提交。不新增生产假Provider。

容器模型链变更后构建本轮镜像，记录源码、不可变镜像ID/架构、安装ID和实际端口；健康与Doctor不消耗模型。真实Key只由用户在独立设置页输入，付费请求需另获明确次数/token/费用预算授权。沿用并扩展现有live_acceptance控制以支持已绑定独立Docker安装的固定内部3081；普通3081实例仍拒绝，不因环境开关推定任务隔离。预算计入重试及工具续调，跨重启总量不能扩大。未授权/缺Key时真实闭环NOT_RUN/PARTIAL，但继续独立免费任务。

真实闭环为公开设置保存Key、创建会话并由固定DSH完成文本研究、冷读结果、无活动任务时重启、同session续问、同镜像重建后凭据/会话/非秘密文件核对、停止并确认实际端口释放。上传CSV不冒充Agent产物。

扩展现有Router/普通CI使相关Python/JS测试真正执行，不新建框架或昂贵平台矩阵。浏览器三场景各一次，失败最多一次定向复现；残留连接状态不是根因结论。不得杀浏览器/未知进程、关闭所有权检查、自动关用户页面或无限延长等待。无法安全修复则保留限制与后续任务。

文档区分容器健康、后端可用、凭据配置、真实调用、文本恢复、脚本沙箱、本机集成、平台/发布就绪。Linux沙箱、Windows ACL、全平台认证、免宿主Python、Registry分发和Office/Wind/Tabbit桥不在范围。真正闭环没有实证就不推荐为已验收路径。

## 自审

Task A-E及Done要求均有对应模块、测试和实际验收阶段；无新依赖或第二引擎，无旧证据改写，无全局配置/框架改造。普通测试与真实模型/设备证据分开；独立安装/付费/远端操作的授权不因设计确认自动扩大。
