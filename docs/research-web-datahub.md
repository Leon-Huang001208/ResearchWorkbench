# Research Web DataHub

DataHub是`app/research_web/datahub/`内的FastAPI进程模块，不是新守护进程、调度器或全局行情数据库。
DSH仍是唯一研究引擎；Web只读资料，原生插件获单次审批后查询同一DataHub。
不导入旧Connector.run、AKShare生命周期或旧报告编译链；没有新增依赖。

## 查询与来源

| source | 固定公开来源 | 范围 |
| --- | --- | --- |
| fund_nav | `https://api.fund.eastmoney.com/f10/lsjz` | 六位code；成对start_date/end_date按实际分页取得范围，最多十年且不含未来；旧limit只取最近一页、最多100条 |
| cls_telegraph | `https://www.cls.cn/api/cache?name=telegraphList` | 最新limit 1–100条公开快照 |
| fund_profile | `https://fundf10.eastmoney.com/jbgk_<code>.html` | 当前基金身份、规模、经理、费率、基准文字等已核实字段；不是历史时点资料 |
| fund_distributions | `https://fundf10.eastmoney.com/fhsp_<code>.html` | 权益登记/除息/发放日期、每10份分红原文；不构建复权总回报 |
| fund_holdings | `https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc` | code、topline=100、year可选1990..当前年；不填year请求最新可用期。仅解析content的JSON字符串，不执行JS |

source/code/limit/start_date/end_date/year/refresh是业务参数；工具不接受会话、目录、URL、头、cookie、代理或凭据。
日期以Asia/Shanghai校验。基金代码保留前后端份额原文，不合并证券身份。
持仓保留报告期、标题、股票代码/名称、占净值比例、万股/万元原文；报告期不等于披露日期，完整持仓覆盖未知。
HTML资料将换行表头仅用于匹配时去空白，原文字段名仍保留；缺闭合td在下一th/td前截断，避免字段串联。
`---（每年）`等缺失保留original_value而value=null，不解读成零费率。
分红每10份金额保留来源原文；币种未独立核实，currency统一null并标记verified_currency缺失，不由“元”或基金代码猜测币种。

## 限额与状态

固定HTTP目的地、不跟重定向、trust_env=False，不继承认证/代理，不自动重试。整体查询15秒；每响应1MiB、总原始响应16MiB、最多100页/5000行。
实际NAV响应的TotalCount/PageSize/PageIndex在顶层，记录在Data.LSJZList。请求100实际可能仅20；不能用“少于请求数量”当完成。
实际页码、页大小、总量和日期逐页验证，重复页/总量或页大小变化停止并保留已经得到的原始响应与解析记录。
无穷值、坏日期、超出请求范围、必填数值缺失均明确失败/不完整。

- `complete`：日期范围请求的来源分页结束且没有已检测到的覆盖异常；不是市场全量的独立验证。
- `snapshot`：单次公开快照已取得，不能宣称完整历史。
- `empty`：来源成功返回零条，和取数失败区分。
- `partial`：已经取得部分可用行但后来失败/触限/冲突；不得自动命中完整缓存。
- `failed`：没有可用行且取数或解析失败；manifest明确标记失败，不伪装报告交付。

同值重复日期去重并记录；唯一日期数少于供应商总量时status=partial，即使来源页确已结束、pagination_complete=true。
冲突日期从可用解析记录移除、不任选其一，原始响应保留。取消立即停止HTTP，不发布快照；私有调用收据保留cancelled。
BFF关闭及现有会话cancel均取消相关请求。原生abort通过独立短超时取消请求联动；取消先到的调用ID写入tombstone。

## 私有控制与会话存储

启动器/服务创建独立随机控制凭据`.control/datahub.json`，0600；父目录0700。
原生可信插件在trustedDirectory沿实际DSH父系验证后、原生审批允许后读取固定文件。
拒绝symlink、hardlink、错误属主或过宽权限；token不进入脚本环境、prompt、普通API或日志，不读取/复用模型密钥。
地址默认`http://127.0.0.1:8088`，首次可信启动可用`--datahub-url http://127.0.0.1:<port>`指定隔离BFF端口；只接受无userinfo/query/fragment/path的回环HTTP origin。已有地址不符报错，不静默覆盖。

```text
.control/datahub.json                         # 新产品控制凭据，只给可信服务/原生插件
.control/calls/<sid>/<call-hash>.json          # 稳定调用ID + 参数指纹 + 受理/结果
.control/snapshots/<sid>/<dataset_id>/         # 原始响应 + 权威manifest
sessions/<sid>/inputs/datasets/<dataset_id>/   # 只读rows.json、rows.csv、manifest.json
```

每次新查询使用独立UUID，临时目录写完后先rename并fsync公共输入，最后rename私有目录作为目录提交标记，不覆盖旧快照。
若进程在两次rename之间退出，公共孤儿目录与私有.pending目录均不进入资料枚举，不阻塞健康资料或新查询，也不自动删除；原pending调用重启后仍不自动重发HTTP。
数据文件创建0600并拒绝链接逃逸；读路径用NOFOLLOW目录描述符逐级打开。
私有manifest作为校验基线，每次目录/详情/分页/下载复核public manifest及解析文件hash。原始文件没有普通Web下载路由，不进附件或报告产物清单。
manifest含schema_version、query、source/source_url、retrieved_at/as_of、字段单位/币种（未知null）、请求/实际日期、行数/总量/页数/分页、coverage、missing/limitations和原始/解析文件相对路径+SHA256。
manifest自身SHA256由详情返回，避免自引用。CSV把外部公式样式文本前置单引号，合法数字不转义；JSON和私有原始响应保留原值。

同会话、同参数、同schema_version的完整请求快照可复用：资讯60秒、NAV/补充资料15分钟，保持原retrieved_at，返回cache_hit=true。
refresh=true始终新建；同原生调用ID重放返回同一结果，同ID不同参数拒绝，重启后pending状态不自动重发。
自动缓存不跨会话。用户显式FinGPT→Claw升级会先校验原资料与原始hash，再复制为新ID、新owner、不用链接、不发HTTP，并保留origin_dataset_id/origin_manifest_sha256及原retrieved_at。
升级draft保留原消息正文，追加旧→新dataset_id映射、原/新manifest hash、原取数时间及当前会话manifest/rows相对路径与文件hash；明确旧路径不适用于新会话，不替换历史正文。

## API契约

- `GET /api/research/data/capabilities`：`{items:[{id,name,source,approval_required,available,schema_version,parameters}],missing}`。
- `GET /api/research/sessions/{sid}/datasets`：`{items:[summary]}`；老会话返回空数组。
- `GET /api/research/sessions/{sid}/datasets/{did}`：完整manifest、manifest_sha256及下载引用。
- `GET .../{did}/rows?offset=0&limit=100`：`{items,offset,limit,total}`，limit最大500。
- `GET .../{did}/files/{rows.json|rows.csv|manifest.json}`：已校验的当前会话数据文件下载。
- `POST /api/research/internal/data/query`：`{session_id,call_id,query}`。
- `POST /api/research/internal/data/cancel`：`{session_id,call_id}`。

所有internal入口在解析请求体之前检查`X-Research-Data-Key`；无认证浏览器不能绕过原生审批取数。
公开GET不发起上游请求。浏览器API仍受现有同源边界限制，无CORS、多用户登录或远程部署支持。
`service.detail.datasets`供SSE/UI：id/dataset_id/name/source/source_url/status/row_count/requested_range/actual_range/pagination_complete/retrieved_at/cache_hit/limitations/missing/pages_fetched/provider_total/as_of/files；不推全部行、fields或raw_files。
files条目包含name/path/sha256/size/url/kind=dataset；url为上述专用下载路径。
原生工具返回字符串字段dataset_id/source/status/manifest_json/files_json/sample_json，最多三行样本；Python从只读路径读取全数据，不把历史全部塞进上下文。

## Skill与研究口径

四个Skill及persona要求：父Agent先批准准备资料，读取manifest核对缺失后，复杂Claw任务再分两个子Agent读取同一数据集，不重复取数。
计算限定已获得数据；累计净值不是总回报指数。未取得期初前一估值日及分红复权口径时只称“首末观测区间净值变动”，不冒称完整日历年度收益。
业绩基准文字不是基准序列；目前未取得可靠基准序列、合同/报告下载服务。20行最近快照不能证明三年表现。
XLSX应包含原始解析记录和公式/计算说明、dataset_id/hash；DOCX/HTML使用同一ID/日期。输入快照不算报告产物。

## 验证与限制

离线：`python -m pytest tests/research_web --confcutdir=tests/research_web -q`及`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`。
还执行ruff/black/isort/mypy及项目任务完整性检查，具体结果见`.ai/reports/2026-09-02-datahub-implementation.md`。
真实来源只读核对由父任务记录在`.ai/reports/2026-09-02-datahub-source-probes.md`，不把离线测试当真实模型闭环。
模型审批→取数→双Agent→报告及Web资料UI仍需父任务集成验收；本后端任务不启动/重启服务，不修改3080、固定DSH、模型、原生额度或Seatbelt权限。
单Web worker、本机macOS；未验证Linux/Windows、多租户、磁盘总配额或大规模快照目录性能。
