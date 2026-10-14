# G2A Docker 模型凭据进度

后续用户明确授权为外部夹具设置上限并保持运行：实际更新为 memory=swap=512MiB、
CPU=1、PIDs=128，核对原 container ID 仍 running 且未 OOM；没有停止或删除它。
DSH 刷新构建成功，干净源码 `8bc8cd8ca910ad89a6cba3c7842bdb19579284b5`，
本地 arm64 runtime image `sha256:24968bc07bb6ec84f789b7c4b4d99d230033f725e7a43270d5420347ca4cb653`，
无 registry manifest digest。完整 DSH 编译、606 包 staging 和最终导入 smoke 通过，builder 退出停止。
候选初始化主密钥成功并实际健康，但 credential-probe 和模型 describe 失败；未报告模型闭环通过。
隔离 Python 导入 credential_backend 时，core.observability 导入全局 Settings，尝试在只读
`/opt/rwb/logs` 创建目录。已增加拒绝全局 Settings 导入的回归，观察到 FAIL 后改为既有标准
日志 handler；保持 -I -B、清洁环境和受管模块路径。修复后的新镜像及产品闭环待验。

基线：master `8a2d4ba75294b3fbe2aa90aa802dfd25a1296a2b`；PR93 head `02a9a0c1aef8244a9c71aa2c32e06e07be4f9878` 已合并。
上述 head 和 master 的三个对应 CI 均实时查询为 success，不沿用 f05c016 的旧证据。
固定 DSH 为 `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`。

dev 名额已受管 stop/cleanup 退休旧 task（保留源码与四卷），新 g2a 绑定本 worktree，3GiB。
stage candidate 停止、登记预留 2GiB；VM 实际 8319238144 bytes，builder 冷构建 5GiB 合同保留。

初始加密/provider/bridge/Native 兼容及 launcher 相关测试：206 PASS、2 Native 实机测试 SKIP。
初次并发测试有一次 runtime_contract_changed，未改守卫，复测通过；不作为 Native 实机证据。
独立管道使用 Python -I -B、cwd=/、清洁环境、合成值，拒绝 ambient/PYTHONPATH 来源。
真实供应商生成、重建后生成、设置页验证、实际新镜像、fixture 隔离与本轮 CI 尚未执行。
未接触其他应用或历史 Key。当前开发中的代码未提交，不宣称 revision 标签完整覆盖构建内容。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"模型凭据复用既有私有桥与固定 DSH provider，增加显式加密存储绑定，不增加研究引擎或任务恢复事实源。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"现有管理平面和单容器双进程保持，增加实例主密钥只读存储挂载及限额初始化步骤，生产提升和完整备份仍未实施。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"现有模型设置和测试路由只增加来源状态投影，不改变 Host 与 DSH 的调用拓扑及活动任务保护。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"模型设置复用现有状态列表展示后端来源，没有新页面或流程分支，Key 不回填与显式清除保持原有交互。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共享 ResearchService 仅增加凭据来源字符串映射，Automation 的调度、原生关联、恢复及模型变更串行保护均未改变。","diagrams":[]} -->

后续扩大检查：228 Python PASS、2 Native 实机 SKIP；132 Node PASS。Ruff 与五个源码文件 mypy PASS。
一次全闭包因 dev /tmp 256MiB 耗尽出现错误，改用本实例 cache 卷放夹具后 102 PASS，
剩余 9 项 Native 恢复/文档生成失败已在未修改主线的同容器复现（9 FAIL、1 PASS）。
不修改无关平台守卫或把这些失败写成 PASS；本次相关 bridge 与隔离测试通过不代替 Native 实机。

实际首次构建输入为干净提交 `3262b0ac5`，平台 linux/arm64。固定 DSH 的完整编译执行，
但 pnpm 的大包下载错误后产生缺失的 libreoffice-kit-wasm 目录，staging 守卫抛出
`dsh_staging_invalid`，没有新 runtime image。构建器 memory=swap=5368709120、CPU quota=200000、
PIDs=256 实际核对，失败退出后 builder 已停止，未删包或跳过 staging。
补了受管 `build --refresh-dsh` 参数（当前未提交/未运行）：显式绕过 dsh-builder 缓存，
保留完整锁、构建检查、限额和退出停止，不清除其他缓存或实例。

恢复 dev 被外部容器 `rwb-hot-probe-6a5d3231` 阻断：其内存上限为 0，manager 返回
`unbounded_running_container`。已再次查询该实际容器仍 running；未停止、删除或修改它。
dev g2a、stage candidate 与 builder 当前均停止；g2a 源码、持久卷和登记名额仍保留。
新凭据主密钥尚未在候选初始化，真实供应商、重建后生成、隔离 helper 与本轮 CI 仍 NOT_RUN。
原始本地构建/状态证据在 `~/.local/share/rwb-docker/logs/g2a/`，合成测试/基线对照日志在
`~/.local/share/rwb-docker/logs/g01/g2a-*.log`。外部夹具结束后，恢复 dev 完成刷新参数测试与提交，
再 stop dev → build --refresh-dsh → stop/replace-image/enable-model-credentials/credential-probe/up。
