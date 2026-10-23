# 长期研究档案与机会预警界面

本模块是现有 Research Web 的 Extension：沿用字体、主题 token、主导航、资产行情和研究输入框，不引入框架或第二研究引擎。实现位于 `ui/dossiers.mjs`，由 `app.mjs` 挂载，样式使用 `dossiers.css`。宿主验收范围是 macOS Web；离线 JS 回归不表示常驻、供应商或其他平台已验证。

## 页面与闭环

- `#/assets?view=dossiers` 为资产观察的二级视图，`dossier=<32位小写hex>` 选择档案。五区为当前判断、观点时间线、证据、催化剂与风险、研究成果。档案列表可显示归档项并读取下一页。
- `#/intel/signals` 展示关注对象的机会、风险与催化剂，保留数据时点、来源、覆盖、缺失与过期提示。没有信号不等于没有风险；数据覆盖未知单独展示。
- 创建、研究记录追加／修订、证据归入、成果关联、归档均由显式动作触发。表单输入按档案保留，409 不覆盖旧判断，刷新后由用户重新确认。证据与成果先展示本地归档预览，确认仍绑定预览时的版本；Host 提交时重新鉴权并核验。
- 继续研究先调用 Host 冻结交接，检查 `auto_send=false`、档案 ID、版本、内容 hash 和 Host 生成的 32 位 opaque `context.handoff_id`；随后进入原 FinGPT／Claw 输入框，保留并追加既有草稿。准备阶段没有调用 create-session、send-message 或模型接口。任何预创建会话（包括 @ 候选、上传或建会话响应丢失后的显式重试）都不携带或绑定 receipt；仅用户实际发送的 prompt body 携带 `dossier_handoff_id`，由 Host 按账号和目标会话鉴权绑定。该授权不从文本解析，不能扩展用户已选来源范围；失败／冲突保留文本、receipt 和重试幂等键，成功首发后清理 pending。清空草稿、切换研究对象与账号变化会清理待发送授权。
- 能力中心现有 Skill 的详情补充六类档案方法的输入、输出结构与限制，继续使用原已发布能力版本及“查看版本”入口；方法说明不授予数据或工具权限。
- 手动扫描只调用档案 scan；持续跟踪默认关闭，只有服务端 `tracking.eligible=true` 才显示可开启状态，服务端仍须重新鉴权和核验资格。

## UI 接口合同

基础域 `/api/research/dossiers`，账户完全由服务端会话确定，UI 不传 owner/root/path。

| 操作 | 路径与形状 |
| --- | --- |
| 列表／详情 | `GET ?include_archived=false&cursor=...` → `{items,next_cursor}`；`GET /{id}` → 档案详情 |
| 创建 | `POST` → `{title,subject:{kind,key,label},idempotency_key}` |
| 修改／归档 | `PATCH /{id}` → `{expected_revision,idempotency_key,title?,archived?}` |
| 记录修订 | `POST /{id}/records` → `{expected_revision,idempotency_key,record_id?,kind,title,body,state,reason,evidence_ids,watch_from?,watch_until?}` |
| 时间线 | `GET /{id}/timeline` → `{items,next_cursor}`；详情的 records 是当前投影 |
| 证据归入 | `POST /{id}/evidence` → `{expected_revision,idempotency_key,source_session_id,reference:{type:dataset|file|source,id},locator?}` |
| 证据读取 | `GET /{id}/evidence/{evidence_id}`；每次由 Host 复核权限和 hash，失败不重新抓取；响应 `{evidence,content,state,truncated,projection?}`，服务端 `truncated=true` 即明确标为部分预览 |
| 成果关联 | `POST /{id}/links` → `{expected_revision,idempotency_key,type:session|report|file,source_session_id,reference_id?}`；质量由 Host 核验；返回条目使用 `type,quality,source_mode`，quality 可为状态字符串或含 status 的对象 |
| 研究交接 | `POST /{id}/handoff` → `{expected_revision,idempotency_key,mode,action}`；返回 `{prompt,mode,auto_send:false,context:{dossier_id,revision,evidence_handles,sha256}}` |
| 信号列表 | `GET /signals` → `{items,coverage,missing}`；每项含 `dossier_id,title,body,kind,state,evidence_ids,as_of,source,coverage,missing,stale` |
| 手动扫描 | `POST /{id}/scan` → `{expected_revision,idempotency_key}`；返回 `{dossier,signals,coverage,missing}` |
| 持续跟踪 | `PATCH /{id}/tracking` → `{expected_revision,idempotency_key,enabled}`；返回 `{dossier,tracking}`；详情 tracking 为 `{enabled,eligible,reason}` |

写入超时保留同一幂等键和 expected_revision；仅在用户显式重试相同操作时复用，不自动重发。409 删除旧尝试凭据但保留输入，刷新取得当前版本后再提交。路由、对象、账户身份和取消代数共同约束迟到响应；切换账户清空旧数据、尝试和草稿。

供应商文本、证据正文、标题、URL 字符串均按文本转义，不注入 HTML。正文预览超过 30,000 字符时明确显示部分预览，不冒充完整证据。MCP 凭据录入由独立受管插件组件负责，不在档案表单中接收秘密。

## 状态与验证边界

加载态保留已确认内容和输入；空态给出下一步；错误提示保留错误和重试入口；无权限隐藏档案正文；过期信号明确标识；并发冲突保留输入、要求刷新；归档只读且可恢复。按钮覆盖默认／聚焦／禁用／处理中，键盘使用原生表单与按钮，内容分区跳转不会改变 hash 路由。窄屏变为单列、长文本换行，颜色来自现有主题。

目标测试为 `node --test tests/javascript/research_web_dossiers.test.mjs`，以及既有 UI、intel、asset、navigation 回归。离线 Chrome 闭环命令为 `node tests/e2e/research_web_dossiers.mjs`，在 1440×900 light、768×1024 dark、390×844 light 检查冲突保留、证据撤权、XSS、扫描缺口、冻结草稿、用户显式发送时的实际 prompt receipt body，@ 候选可预创建普通会话但零绑定、键盘返回及横向溢出。日志写入 `logs/research-web-dossiers-ui.jsonl`，截图和回执在 `outputs/research-web-dossiers/`；夹具产生的 409／403 作为预期错误单独计数。浏览器 fixture 与截图不替代登录态候选安装和业务保全；真实模型、收费 MCP、常驻部署及 Windows/Linux 原生保持独立验收。

合同夹具 `tests/fixtures/research_web_dossier_contract.json` 由当前真实 `DossierService` 与临时 `Store` 离线生成，记录 producer 源文件 SHA。报告质量投影明确为 fixture-only，不作为真实报告验收。档案／记录／证据为32hex，来源会话独立保留36位UUID；时间线读取 payload，证据状态读取 state/error_code，ISO观察窗口在日期编辑中保留原时分秒与时区。403 会清理正文缓存并阻止迟到响应重新填入，渲染侧再次拒绝展示。

Prompt 已获接收后，receipt 清理同时检查内存草稿及固定的 `new:claw`／`new:fingpt` 持久首页草稿，覆盖 @ 预创建后刷新目标会话的情况；只清相同 receipt，保留文字和其他新 receipt。
