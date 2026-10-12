# G2A Docker 模型凭据进度

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
