# 长期研究档案与机会预警实施合同

用户已批准完整方案。本任务为 macOS Web 功能开发，保持唯一 DSH、原质量门、个人根和现有报告正文库；新 SQLite 仅存档案元数据，不连接正式 PostgreSQL，不引入依赖。供应商凭据、收费实测、正式数据库操作和常驻部署另行授权。

## 共同 API 合同

接口位于 `/api/research/dossiers`，由当前 ResearchService 的个人 Store.root 决定归属，客户端不能传 owner/root/path。

- `GET /` 返回 `{items: [...], next_cursor: null}`；支持 `include_archived`，有界分页。
- `POST /` 接收 `{title, subject:{kind:company|industry|theme,key,label}, idempotency_key}`，返回档案详情。
- `GET /{id}` 返回 `{id,title,subject,revision,archived,updated_at,records:[],evidence:[],links:[]}`。
- `PATCH /{id}` 接收 `{expected_revision,idempotency_key,title?,archived?}`。
- `POST /{id}/records` 接收 `{expected_revision,idempotency_key,record_id?,kind:opinion|catalyst|risk|note|signal,title,body,state:open|supported|refuted|resolved|dismissed,reason,evidence_ids:[],watch_from?,watch_until?}`；同 record_id 追加版本，不覆盖旧记录。
- `GET /{id}/timeline` 返回 `{items:[],next_cursor:null}`，支持记录类型/状态过滤；原始版本可追溯。
- `POST /{id}/evidence` 接收 `{expected_revision,idempotency_key,source_session_id,reference:{type:dataset|file|source,id},locator?}`；来源、hash、授权、时点均由 Host 解析，不信客户端声明。文件 reference.id 为受控会话相对路径，拒绝逃逸/符号链接。
- `GET /{id}/evidence/{evidence_id}` 每次鉴权并检查当前字节；返回证据元数据/受控正文投影；缺失、变化、撤权明确报错，不重取替换。
- `POST /{id}/links` 绑定 Host 已存在的会话/报告/文件，重新核验质量状态，不信客户端传 passed。
- `POST /{id}/handoff` 接收 `{expected_revision,idempotency_key,mode:fingpt|claw,action:company|industry|research_prep|update_view|check_risk|earnings_gap}`；返回 `{prompt,mode,auto_send:false,context:{dossier_id,revision,evidence_handles,sha256}}`，只准备冻结上下文，不调用模型。

实施细化：context另含32hex `handoff_id` 与必要source_scope；只有用户实际发送 `Prompt.dossier_handoff_id` 才绑定单一Host sid，同sid幂等、跨sid拒绝。普通NewSession、输入@触发的会话创建与草稿文字均不绑定权限。runtime preflight收到精确source operation/ID，只为该sid已绑定且重新鉴权的档案来源开放读取；原web范围限制保持。links可用已登记Host opaque文件ID或对应受控相对路径，source_mode和quality均从Host获取。

详情中的 records 为最新投影，timeline 保留所有修订。所有写入验证 expected_revision 和幂等键；重复键相同请求返回原结果，不同请求/版本冲突 409；失败事务不推进版本。日期 ISO8601，未知公开时间保持 null，不能用取得时间冒充 PIT。

## 保全与安全

证据引用和 retention pin 同事务落库；通过 RWB 的 Host/原生日志永久清理均在删除前持统一锁检查引用。软删会话保留 pin。归档不等于删除，不提供默认强制删除。历史文件从外部删除时保留身份并显示缺失。跨会话引用复用原始字节，不复制为新正文；读取与导出复查权限。

新根和 SQLite 进入备份/恢复/业务保全清单；备份使用 SQLite 一致快照及证据引用校验，恢复失败保留旧指针。操作日志仅记录 ID/版本/来源和稳定错误码。

## 页面与阶段

资产观察增加 `#/assets?view=dossiers` 二级视图；选中档案用 dossier 参数。研究情报增加 `#/intel/signals`。不新增一级菜单，保留所有旧路由、主题、表格和研究面板。

1. 档案后端/版本/证据保全及近处回归。
2. 档案 UI、冻结研究草稿、已有方法入口；机会/风险的有证据手动扫描。
3. 小创受管 MCP 静态 Bearer 安全录入、固定评估授权/积分状态及原件入链。18 次/54 子弹仅为未来需单独批准的实测计划；本次只离线夹具。
4. 默认关闭的既有调度接入，手动合格后允许用户开启；只有新/变化/解除通知，不自动改观点。

公开 UI 与 Python/API、跨租户、幂等、并发、故障恢复、purge pin 竞态、hash/时点、费用未知与取消、响应截断和迟到响应都需回归。完整 changed set Router、独立 Python/JS/安全评审、原 CI 与同候选 macOS 干净安装保留；真实模型、收费供应商、部署和其他平台证据独立。
