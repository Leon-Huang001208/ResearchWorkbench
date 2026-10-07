# Task14 当前主线本地冲突集成

宿主 macOS；任务为现有功能的本地集成。当前主线为
`205d2a170d9ece9c2751e014b63abe326510ab9c`，目标为
`5be67d4d3b4d8d19cbf509e949c9ad9491031ab3`，共同基线为
`c24a8a161674678d572bf9ac35fab30489b40605`。仅操作指定 b1 worktree；
不执行远端写入、Docker 重建、物理生命周期、全局配置或其他平台适配。

## 合并决定

保留目标分支的自动端口、EndpointStore CAS、fresh-root 调用内证明、Foreign Native
Ledger 的真实 lease/scope/FD 复查、Docker tmpfs/logs 布局、45 秒 Native stop 端口释放
等待和现有 runtime_state 安全门。runtime_mode.py 与目标提交字节一致；service_manager、
docker_runtime、web_bootstrap 相对目标仅加入主线统一 platform_capabilities 投影。
测试夹具同时复制 runtime_endpoints 与 platform_capabilities，不改认证或失败关闭行为。

保留主线平台任务证据内核、能力支持边界、文档安全 reader、平台阶段与能力矩阵，以及
已验证的 Debian 官方源 HTTPS 传输。Dockerfile 仅组合目标既有本地 Node headers 方案与
主线 HTTPS 指令，不改变锁、APT 仓库、签名或代理。安装文档移除过期“仅 Native”范围及
“HTTPS 未授权”陈述，保留原合同；支持矩阵仅同步上述现有实现，不升级支持声明。

生成 Python 索引、Atlas 与 index 使用现有生成器；不改生成器、图源、截图或视觉回执。
reading.repository.revision 先保留已发布主线 3dfdefeea；新增 endpoint/control 文件不在
该旧快照，当前链接不能称为完整。先冻结真实 merge，再以独立文档提交绑定该已存在 SHA。

## 实际验证和限制

首次 pytest 因未限定 Web conftest 边界在收集前缺 SQLAlchemy，退出 4；随后按项目原入口
加入 `--confcutdir=tests/research_web`，使用原 Web venv 和当前 worktree PYTHONPATH。
未安装依赖。首次 constraints 使用不支持的 --base 参数失败；后续使用完整 changed-file 集。
首次架构门仅拒绝缺少新映射的支持矩阵文档变化；按主任务授权补充准确说明，不放宽门禁。

目标分支的物理 Native→Docker→Native PASS 及既有 broad gate 证据保留历史归属。
本合并不把它们升格为新合并提交的物理验收。新镜像构建曾在目标源码因 pnpm metadata
HTTP 超时、SOCKS Undici unsupported 终结；本轮不重试。远端 CI、干净安装、最终镜像和
Windows/Linux 真机证据保持未验证，由主任务和相应平台任务继续。

本轮实际命令、测试结果与冻结哈希保存在本 worktree `logs/task14-b1-*`；完整基线 changed
set 由只读 planner 发现，保持 L4 和原全部外部门。当前工作只是本地合并验证，不是完整交付。

已实际执行：平台任务/回执/摘要及 Docker JS 合同 53 PASS；架构/文档/规划 JS 合同
157 PASS；安全平台文档 reader 26 Python PASS（1 项已存在 Starlette 弃用警告）。
4 份冲突 Python 文件 Ruff、Black --check、isort --check-only 全部通过；Python index、
Atlas --check、Markdown 治理、当前基线架构门及完整 changed-file Project Constraints 通过。

首次五模块 Python 合并运行 870 PASS / 3 FAIL，104.68 秒；失败分别为 busy-preferred
分配、bind-race 三次预算和 installer-summary 回滚，先报告 mode 读取变化后拒绝。
未改变源或测试，单独重跑相同三项 3 PASS / 4.27 秒；原失败日志保留，不把这次结果
描述为原合并运行全部通过。整个 Docker 模块独立复查为 316 PASS / 90.31 秒；
说明三个失败未在隔离模块中复现，原因未确证，不据此修改生产安全门或抹去首次证据。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"组合既有端口事务与私有账本、tmpfs及平台能力投影，不改变部署节点、认证安全门和单一DSH边界。","diagrams":[]} -->
