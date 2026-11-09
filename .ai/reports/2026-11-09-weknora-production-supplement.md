# WeKnora 私网生产补丁

Mac mini 原生 Web 开发。原 PR #289 的隔离验收已通过，HTTPS 网关授权和主账号原位挂载
仍需本补丁。跨站浏览器只允许精确的 WeKnora 授权入口及登录页，忽略已有 Cookie。
同一 HTTPS 主机的不同端口因共享 Cookie 被拒绝。主账号复用原目录和已登记端口，
取得旧 supervisor/lifecycle 锁后确认旧 Native 与 Docker 停止，已有影子目录时拒绝挂载。
主 Web 子进程继承同一个内核锁，网关退出后仍阻止第二个写入者。固定生产前版确认含同一锁协议。
测试第一轮复现旧 Cookie 重定向循环，修复后同批 12 项通过，失败回执保留。

<!-- architecture-review {"group":"inbound-mcp-readonly","structure":"changed","reason":"私网 HTTPS 授权新增精确 WeKnora 跨站导航边界，工具及冻结证据授权继续复用原服务。","diagrams":["15-inbound-mcp"]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"changed","reason":"新账户网关以同一运行池原位管理主账号 Web，并通过原生命周期锁排除双写。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"研发进展更新可见范围，认证和状态展示沿既有组件，未改变前端运行边界。","diagrams":[]} -->

<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"原主账号的唯一 Web 子进程继承生命周期文件锁，网关故障期间仍与原 Native 和 Docker 管理器互斥。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"内核锁继承扩展主 Web 生命周期保护，未改变研究 API 路由、证据访问或数据流。","diagrams":[]} -->

独立复核已确认关闭 Docker 互斥和网关退出后双写两项缺口。当前前版 `1315d11a` 的 Git 树使用同一 guard 协议。
WIP 的 POSIX 实锁、真实 Web 子进程、HTTPS OAuth 目标共 5 项通过。该批因传入一条参数化选择器实际展开两例，证据回收计数不符，已保留原始结果和登记根。
生产仍待独立执行器验证同一候选的前进与固定前版回滚，且需确定实际 WeKnora 回调的可达入口。

同一登记根内的独立定点复测共 18 项通过，包括旧锁协议不明时拒绝、Native/Docker 静止判断、
实际内核锁继承、主账号历史读取与 HTTPS OAuth。保留未通过回收认证的原批次。

通用 CI 默认浅克隆，本机使用同一 shallow 边界复现集成夹具找不到历史保护提交。
夹具改用其合成安装版本作为最低版本，继续执行真实 Git 祖先检查。生产仍验证固定历史门，
另用已安装的 `1315d11a` 实际验证新网关崩溃时旧写入者拒绝进入，子进程退出后才可取得原锁。
