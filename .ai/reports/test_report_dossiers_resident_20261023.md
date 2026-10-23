# 档案固定部署任务

宿主macOS，任务dossiers-resident-20261023-514d61ac，Web常驻部署功能。用户明确授权补齐受审入口后部署并验收；不含收费实测。

档案固定部署使用 `apply-dossiers`／`reviewed-research-dossiers-v1`：前版固定已核验 `5343e18d9f203a87f2d958218e4288afa527711f`，产品固定已合并 PR209 `56709a8dbb6e01d2ab17b64533319e199ebef86f`。复用原 version4 维护锁、BirthFence、Native／RuntimePool／市场及 DataHub 空闲检查、全账号64MiB业务索引与档案保全和恢复；依赖锁、DSH、自动兼容清单、凭据及付费调用保持原合同。源码、CI、实际服务切换和登录后跨会话验收分别留证，未执行的层级不标通过。

## 已观察

只读现场accepted与网关resident均5343e18d；verify_primary精确5343成功并证明当时无研究活动。旧gateway status历史receipt仍5df，不以其认证现场版本。requirements/web.lock、web.in及DSH pin在5343与56709a8之间无差异。

红例：新profile矩阵34failed/60errors（实现前缺少模式），原日志保留；实现后全模块1367passed/1warning，105.05秒。黑格式器已执行。最终候选Router／独评／CI／部署／真实浏览器状态另绑定，当前未执行不得冒称通过。

## 边界

只固定新profile，不修改旧profile、controller/evidence字节、自动兼容白名单和恢复协议。新的档案HTTP与数据路径属于既有PR209，不在本次更改。持久业务与凭据保护；忙碌或未知不停止服务。Chrome其他任务已预约窗口期间不操作其窗口或标签1512777099。
