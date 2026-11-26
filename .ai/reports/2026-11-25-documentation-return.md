# 隔离文档返回 Research Web

实际复现：带 Sec-Fetch-Site=cross-site 的顶层首页导航返回403；来自 CSP sandbox 的链接即具有此状态。
首页首跳可能没有 Strict Cookie，故只给严格限定的 GET / 顶层用户点击返回静态同源重入页，
固定 location.replace("/")。该页不读取账号、不签 Cookie；后续正常首页照常鉴权。
测试覆盖有/无会话、iframe、fetch、Origin:null 与API拒绝，文档 Cookie 权限不扩大。
此修复仅需更新网关，原主实例与运行服务不重启。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"只修复现有网关首页导航与Strict Cookie重入，API、认证和运行拓扑保持，安全合同已同步。","diagrams":[]} -->
