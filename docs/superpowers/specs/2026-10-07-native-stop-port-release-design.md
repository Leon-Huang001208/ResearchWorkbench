# Native 停止后的有界端口释放等待

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在既有安全切换的成功 Native stop 与最终检查之间等待原端口可 bind，不新增部署节点、权限或持久状态。","diagrams":[]} -->

用户已确认：最多等待 45 秒；最终严格检查与 CAS 不变；超时继续拒绝。

## 范围与边界

只有 selected mode 为 Native、现有 NativeRuntime 的初始可信状态为 running、明确指定
`--stop-current` 且公开 Native stop 返回成功，才等待本次停止前捕获的原 Native 两个端口。
不等待 Docker 内部端口或异根实例端口，不停止未知服务，不给已停止／未知实例新增权限。

等待位于公开 stop 的生命周期锁退出后、原 switch_select 最终 scope/lease 建立前。
使用既有 `port_busy` 普通 bind，绝不加 SO_REUSEADDR、不移除保留端口判定。
等候本身不捕获、刷新或传递 ForeignLedger 权限。deadline 采用 monotonic、上限45秒；
每次睡眠不超过剩余期限。内部 wait_timeout 非有限数、bool、负数或大于45时在 stop 前拒绝。

端口可 bind 后继续原有 fresh status、归属、foreign observation 和 mode CAS。
端口仍占用、事实未知、元数据被并发修改或新实例出现时仍失败；超时使用既有
`runtime_stop_failed`，mode 保持原值。无自动启动、模式强写、状态清理或重装。
已有 timeout 参数默认从未生效的10秒改为已确认的45秒；不新增 CLI 参数或配置。

## 验收

先 RED→GREEN：有界释放成功、持续 bound/nonlisten 超时、无 stop 成功不等待、
未知初始状态不停止、不等待外部默认端口、mode/CAS 变化拒绝、非法期限 stop前拒绝。
保留真实 socket 的 active-bound 对照，不能把 TIME_WAIT 与 active reservation 都视为空闲。
执行 planner 所选本地门并做规格／Python安全审查；测试不替代真实 macOS 切换。

最后由主任务在既有测试 HOME、fixture、accepted guest image 上执行真实活跃
Native→Docker→Native 与数据／control token 保持、合成凭据持久化和正常删除。
明确 host CLI source 与未变的 guest image source；不伪报新镜像构建。
新依赖、全局配置、Harness、未知服务、远端操作不在本设计授权范围。
