# 档案固定部署任务

宿主macOS，任务dossiers-resident-20261023-514d61ac，Web常驻部署功能。用户明确授权补齐受审入口后部署并验收；不含收费实测。

档案固定部署使用 `apply-dossiers`／`reviewed-research-dossiers-v1`：前版固定已核验 `5343e18d9f203a87f2d958218e4288afa527711f`，产品固定包含 PR209／PR212／PR213 的已合并主线 `1780064b712afb61ff18f2f1811650fc31fd3038`。复用原 version4 维护锁、BirthFence、Native／RuntimePool／市场及 DataHub 空闲检查、全账号64MiB业务索引与档案保全和恢复；依赖锁、DSH、自动兼容清单、凭据及付费调用保持原合同。源码、CI、实际服务切换和登录后跨会话验收分别留证，未执行的层级不标通过。

## 已观察

只读现场accepted与网关resident均5343e18d；verify_primary精确5343成功并证明当时无研究活动。旧gateway status历史receipt仍5df，不以其认证现场版本。requirements/web.lock、web.in及DSH pin在5343与56709a8之间无差异。

红例：新profile矩阵34failed/60errors（实现前缺少模式），原日志保留；实现后全模块1367passed/1warning，105.05秒。黑格式器已执行。最终候选Router／独评／CI／部署／真实浏览器状态另绑定，当前未执行不得冒称通过。

## 边界

固定新profile，保留旧profile、controller/evidence字节、自动兼容白名单和version4 journal；新恢复包的内部manifest补充经过验证的永久冻结源身份。新的档案HTTP与数据路径属于既有PR209，不在本次更改。持久业务与凭据保护；忙碌或未知不停止服务。Chrome其他任务已预约窗口期间不操作其窗口或标签1512777099。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"只增加原Native联合操作员的固定档案profile，继续同一Host／网关／唯一DSH与version4维护和恢复；新增路由及SQLite属于已审PR209，本次无新节点或数据边，原图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"档案profile复用全账号64MiB业务索引与档案元数据、引用和保留标记保全、BirthFence和池空闲门，不新增账号权限、共享数据或后台任务，原安全边界和图保持。","diagrams":[]} -->

完整constraints首次拒绝缺少两项structure decision及ETF原模块说明；补齐决策和模块说明，源／测试字节保持，重新绑定最终候选验证。原失败保留，不删门。


主线PR210前进后正常合并固定ETF-v2与档案两模式；测试parametrize冲突首次组合脚本未通过语法检查，shell未停止误提交本地冲突标记。该提交未发布，已追加修复保留历史并启用失败即停止；重新做语法、标记、全矩阵与最终候选验证，不重写历史或弱化门。


专项独评发现HIGH：旧5343 wheel不含dossier_preservation，而旧恢复pyz只含resident模块。修复新包manifest绑定永久artifact_source，journal/自身摘要/版本/模式/精确源身份/Git干净校验在app导入前完成，父进程仅改sys.path，不改变旧服务PYTHONPATH；旧历史包格式兼容、新两模式缺source拒绝。先以fixture环境得到1通过/5退出码断言失败（实际正确blocked退出1，已修测试错误预期），再用实际配置的5343 primary venv完成6项真实zipapp子进程反例54.47秒；未安装依赖、未变更生产数据、未停止服务。

主线后续合入PR212 WGC与PR213资产图表修复，封闭产品pin更新为1780064b712afb61ff18f2f1811650fc31fd3038以保留已审主线功能；不得用567旧pin忽略新增源码或放宽逐blob冻结检查。既有ETF-v2历史pin保持567，新候选重新执行全部本机门与同候选CI。
