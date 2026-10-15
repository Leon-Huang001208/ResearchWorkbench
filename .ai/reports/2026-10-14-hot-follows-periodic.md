# Hot关注与周期简报接续

宿主macOS，功能开发；worktree hot-intel-continuation，父候选d6b0cb873。完整Goal仍INCOMPLETE，预算不增加，本轮模型调用0。

## 已实现与实际证据

- schema19：关注/不可变版本/审计及条件重放；频道、事件、关键词、机构、资产。原事件ID合并后仍沿既有别名解析。
- schema20：默认停用的周期计划、明确启用、唯一Hot heartbeat/pg-boss hot.brief、固定due/窗口、不可变选材、周期身份、跳过周期与错误/队列状态。Automation只管理适配，不写旧Store周期事实。
- 正常Native schema19关注：follows-live-receipt.json，owner generation58；GET/POST/重放/暂停通过，缺用户动作403；测试关注最后暂停，worker受管停止。
- schema20 PG回归：periodic-final-pg.log，7 PASS；同一周期只冻一次、重启复用、停用取消、官方资料固定版本、controller最小权限、worker拒绝控制、原件更正不覆盖旧简报。
- 慢brief INSERT与空窗口run UPDATE反例先RED（Missing expected rejection），补所有写前/写后claim/owner/计划/signal检查后GREEN。插入/更新notice证明实际到达0.5s慢写，0.2s租约过期整事务回滚。
- Python45 PASS（periodic-final-python.log），UI86 PASS（periodic-final-ui.log），TypeScript检查PASS（periodic-final-typecheck.log）；Python日期偏移/溢出反例与RPC真实方法白名单已补。

## 审查与未验证

关注入口白名单HIGH已关闭；关注两项过期响应P2已关闭；简报发布P1已关闭。空/取消终态写后检查P2已关闭，Python与TS限定审查无阻断。
原PG已通过正常setup升级schema20。正常Native周期运行：Macro冻结完成，MD2122字节/DOCX38203字节/30段并校验计划/run身份；AI窗口真实为空，其唯一已有AI事件发表于2025-02-28，超出一年窗口，未放宽条件。periodic-reconciled-receipt.json为准确回执；首次两频道均产物断言失败记录保留。真实Hot组件+原PG+独立Host适配的浏览器创建/启停/历史/关注暂停通过，错误console0；此范围不等于最终安装主应用验证。最新最终Docker整镜像、当前候选Mac CI、最新联合恢复、当前AI事件及完整要求审计尚未完成。原数据/原镜像/五卷保留；本轮未停止dev/g2b。
此前PG fixture留下的随机schema/角色保留；新fixture核对自己instance/token后精确清理自己新建schema/角色，不扫描或删除历史未知资源。

## 下一动作

当前测试计划与关注均暂停，组件server及worker已受管停止；原预算读取仍17calls/76804tokens/10253microUSD、20/100000/USD1上限。继续当前AI事件的有界受控处理、最新联合恢复、最终Docker/当前Mac CI和完整要求审计，新增调用必须使用剩余原额度。

<!-- architecture-review {"group": "hot", "structure": "unchanged", "reason": "在现有Hot PG schema内增加关注和周期业务表/接口；唯一worker、pg-boss队列、controller授权与ResearchService归属保持，没有新服务或第二存储。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "现有Automation管理入口转接Hot列表/条件配置/运行读取；Hot为周期事实与唯一调度归属，既有Automation执行和Store模型保持。", "diagrams": []} -->

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "既有研究情报及Automation页面增加关注和周期表单/卡片；原生组件、主题、导航根与明确动作边界保持，不迁移框架。", "diagrams": []} -->

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "HotManager新增受控读写操作白名单和字段/回执校验；Native/Docker进程、凭据与安装拓扑保持，schema变化经停止态setup执行。", "diagrams": []} -->
