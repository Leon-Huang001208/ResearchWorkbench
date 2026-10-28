# 自选股票 CSV 导入

资产观察的“更多 → 自选与最近观察”内可选择目标列表和 CSV，预览全部行，选择规范实体或明确跳过，再重新冻结预览并确认追加。没有列表时先使用原“新建自选列表”。导入保留原项 ID、名称、顺序、时间与轮询设置；不创建研究、观察、提醒、调度或模型调用。

## 文件与身份

仅接受 UTF-8（可含 BOM）、CRLF、标准 CSV 引号。固定三列表头为 `asset,asset_type,name`，不允许多列、重复或其他表头。最大 1 MiB、1000 数据行、每字段 120 字符；空文件、无数据行、无效编码、未闭合引号、控制字符与字段内换行均拒绝。trim 后以 `= + - @` 开头的字段作为公式型输入拒绝，不执行或导出 HTML。代码按文本保存前导零；文件名仅在当前浏览器页面显示，不作为服务器文件路径。

首批只支持本账户已获准、本地完整目录中的 `stock`、六位 `SH/SZ/BJ` 规范身份。规范代码精确匹配且名称一致（或空）可直接核验；裸码、名称、同名多候选及名称不符必须显式选择。候选仅精确代码或名称匹配，不使用模糊搜索。每行最多显示 50 个真实候选，并显示总数及截断；未显示实体需更正 CSV 为规范代码后重新预览，不能任意注入选择。名称不作去重键。

ETF、fund、index、industry、theme 均逐行标明尚无规范目录，保留为后续能力清单；本批不猜身份、不新增目录、不接供应商。未解析、不支持和旧项类型/重复完整性冲突必须处理或明确跳过。文件内相同规范实体后续行标为跳过重复；已存在同类型实体标为跳过已存在，不改旧项名称。

## 离线目录与账户

`AssetDirectory.offline_snapshot()` 每次独立读取既有安全缓存，复用原目录类型、完整性与当前资格校验；不调用 `search`、`_refresh`、loader 或 SDK，不启动刷新任务，不改变在线搜索 reader。目录缺失、损坏、撤权或超过既有 24 小时 TTL 时不能确认。

资格指纹沿原 `DataHub.directory_fingerprint`，可能读取既有本地凭据的配置状态；导入不接收新秘密、不读取源查询 token、不向供应商发送请求。测试使用受控内存资格和外部 fail-on-call，不代表真实供应商可用。

账户继续由现有网关身份、页账户匹配、tenant backend key 和逐用户 Store root 隔离。后端只使用当前 `request.app.state.research`，不接受 owner/root/account 参数，不返回根路径；其他账户的列表或预览按资源不存在处理。

## HTTP 合同

两端点均为 strict JSON，额外字段、bool/int 混用及错误类型拒绝：

| Method / 路径 | 请求 | 结果 |
| --- | --- | --- |
| POST `/api/research/watchlists/{watchlist_id}/imports/preview` | `schema_version:1`、`file_base64`、原始字节 `file_sha256`、可选 `selections:{数据行号:规范asset}` 与 `skipped_rows:[数据行号]` | 服务端 UUID、完整行/文件行号、原始三字段、候选/状态/决定、目录状态、目标/文件摘要、30分钟 TTL 与 `preview_digest` |
| POST `/api/research/watchlists/{watchlist_id}/imports/{import_id}/confirm` | 仅 `schema_version:1`、`preview_digest`、`confirmed:true`；`Idempotency-Key` 为 8–128 个 ASCII 字母数字或 `._:-` | `committed` 或全跳过的 `no_changes` 回执，新增 ID/数量、跳过数量、提交前后目标摘要 |

预览只写导入元数据，不写自选项。同目标、同原始文件重新冻结会使旧未提交预览失效；修改选择后不能沿用旧确认。确认在同步临界区重验账户资格、manifest 摘要、TTL、完整目标记录摘要及目录内容/资格摘要。任何变化整批 409、零新增，要求重新预览。

同幂等键同 payload（scope/target/import/digest）先返回已提交回执，不因旧 TTL 或目标已更新再次追加；不同 payload 409。同预览不同键返回同一提交回执，两个预览看到同目标版本仅一个可提交。当前授权先于回执读取。提交后网络响应丢失可用原键重试；不会自动重发。

## 同 Host 保存边界

沿原 `ResearchService → AssetWorkspace → Store`，新增 `index.json.watchlist_imports` 版本化 namespace。预备新目标列表与回执，临界区只替换该目标和导入 namespace 两个引用，同一索引一次原子 save；不循环调用单项 API、不覆盖整份业务字典。

同一个 Store 实例的 `write_lock` 为共享 `threading.RLock`。原 create/add 及 preview/confirm 从读取/CAS 到 stage/save/rollback 全程持锁；`Store.save` 从 payload 构建、JSON、flush/fsync、replace 到临时文件清理也持该锁并可重入。真实后台 `Store.files()` 可先登记其非目标文件，但其 save 等待本批提交或回滚后序列化，不能偷发布失败批次。失败只还原本批两个引用，保留其他会话、文件、模型、查询、通知和列表更新；新建列表失败也撤销本次插入。

这不使所有业务方法成为通用线程事务：现有 Automation 全 Store 快照回退仍仅按原事件循环同步入口使用，不能将其任意线程化。第二 Store 实例、共享 root 的多 Host/多进程、任意外部改索引不受此锁保护。原 Store 无父目录 fsync，因此不保证断电持久性；这些能力保持未验收，不以“无 await”代替线程或跨进程证据。

## 容量、隐私与恢复

namespace 总预算为 8 MiB（包含活动/已提交记录和幂等键），最多 20 个未过期、未被替代的活动预览。过期未提交预览可回收；被替代预览仍受总预算。已提交记录压缩为文件/预览/目录/目标摘要、逐行决定及新增 ID/回执，不保留 CSV 原文或候选名称；不会为腾空间删除已提交幂等回执。达到总预算时拒绝新预览/新键，已有键的只读重放保持。

日志沿项目设施进入 `logs/`，仅事件码、不透明 ID、摘要、数量或异常类型，不记录 CSV 正文、名称、凭据或绝对账户根。前端使用转义和文本节点，known 错误映射中文，未知错误不回显异常或路径。浏览器只在当前页面账户内保存已获用户选择的 File/字节；重绘时保留原控件或复用同一已授权 File 恢复 FileList，账户切换不接受旧异步响应，不写 localStorage。

完整 `index.json` 备份覆盖自选与幂等回执；恢复必须核对原字节、SHA 和权限。DataHub SQLite 备份不覆盖此 JSON，不能替代。撤销已导入项不在本批范围。

## 验收边界

真实临时 Store/ResearchService/create_app、后台 files 线程、有限写入故障、同键/多预览/旧 writer、重建读取及真实 tenant backend 隔离均由 `test_watchlist_import.py` 验证；新 Node 合同与原自选回归另验。loopback-only `tests/e2e/research_web_watchlist_import.mjs` 使用真实 Host 与 Chrome，验证全行预览、键盘消歧/skip/refreeze、原自选追加、冲突输入保留、中文错误、同 File 再预览和 390px 浅深色长文本；外部 URL/供应商/模型均拒绝。

源码、本机证据、独立评审、完整 Router、同候选 macOS 干净安装与常驻部署分别认证；Windows/Linux 原生及真实供应商/模型、跨 Host 与断电恢复不由本批测试认定通过。它是 T5 股票导入有限 slice，不是全部 T5 或全资产目录完成。
