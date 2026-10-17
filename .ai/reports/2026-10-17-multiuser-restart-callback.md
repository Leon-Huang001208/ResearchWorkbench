# 私网用户实例重启回调恢复

宿主 macOS，功能修复；仅本平台与通用仓库门，其他平台产品验收 NOT_RUN。

实际双浏览器验证已通过登录、自己会话/附件读取和跨用户拒绝，但新网关正常重启后用户实例启动失败。原会话、文件、模型配置和旧进程均保持；失败回执留在本机私有目录，不覆盖为PASS。

根因：RuntimePool每次随机选择新Web端口，而DataHub可信回调URL已持久化在用户.control记录。启动器load_control拒绝覆盖不同地址，launcher_prepare抛StoreError。对失败测试用户的同一控制记录调用不同地址已只读复现invalid_resource，原控制字节未变。

修复：只读解析已有DataHub/MCP控制记录，复用共同的严格IPv4回环端口并先占住socket；没有记录时仍新分配。未完成原址事务、未知占用、权限异常、链接、非法token或不同控制原址失败关闭；不改控制记录/token，不认领或停止未知监听。分开登记已预留socket，后续预留失败也会释放。网关日志增加稳定错误码，禁止原始控制内容。

回归8项先因缺少helper失败；随后运行时21项通过，新增跨pool重建验证原端口/控制字节保持且gateway私钥轮换。完整当前候选验收与部署后真实重启仍须完成，不冒充通过；不进行模型生成。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"只在既有逐用户Web/DSH pair内复用已认证的回调端口，组件、存储schema、执行引擎和网络边界不增加。","diagrams":[]} -->
