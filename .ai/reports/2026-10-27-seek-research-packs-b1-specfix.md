# B1 SPEC修波：历史只读证书与独立输出审计合同

任务seek-packs-20261027-7bda5752；macOS Mac mini Web开发；本波base
`b67306ca08c108cb9eee53b5cded8d04959014c2`。只本地修改／验证／scope commit，待root完整
复SPEC→Python／TS QUALITY；未push、merge、部署、启动生产profile或调用真实模型／供应商。
原A6纯核、baseline.json、contracts.json不改；UI／140完整映射不在本波。

## Important 1：历史只读不是执行豁免

先新增真实Dossier链RED，4 FAIL／2原拒绝PASS。按受审
`/tmp/rwb-parity-pack-history-read-design-20261027.md` 实现：

- Catalog原per-user JSON增加server-only `pack_read_equivalences`。直接证固定schema/policy/
  operation/issuer，绑定owner根、九CID、from/to完整record、两端真实immutable tree、manifest/
  runtime及静态资源摘要、解释器/ABI/platform/6依赖等价事实与publication identity。所有必需
  字段从受管state／FS／当前Host运行指纹重算；不是信self-hash或客户端passed字段。
- 发证放进原 `_activate` pending→native投影→终态catalog save，和row/pending终态一次提交。
  中断/故障不留有效证；旧record/tree不写，原enabled/disabled保留。无新DB／秘密库／HTTP输入。
- 每个retained endpoint独立和新target重验、签直接证；v1→v2与v2→v3不能拼接。多次搬迁若有
  v1→v3，必须是该次事务重新核v1/v3发出的直接证；删该证只留两边时拒绝。
- Dossier dataset仅调用专用内部snapshot-read adapter。保留原三参 `_data_query_admission`
  与严格 `_effective_records`；仓库storage_read仍走旧执行/query门，不获得历史读取模式。
  声明／provider binding／频率／复权／PIT检查抽成无写helper，顺序和原拒绝语义保持。
- source-only和target均核pack当前enabled/builtin/origin/no-draft/空bindings、当前真实代码／
  native投影／runtime，重验source scope/config/auth／snapshot／query／provider／raw hash。
  raw读回后再检当前状态与授权，避免只借preflight。旧source普通读取不新增任务能力门；
  三参legacy fallback正常调用，adapter运行异常不降级跳过。
- 原refs先查冲突／混合，不能由按ID去重吞掉。没有receipt时从Host私有prepared handoff、
  context文件、seal与scenario.capabilities补权威；不从client JSON补。沿原visited/verified
  lineage，adapter不重新打开trusted_context，不用ContextVar或全局临时admission。
- 旧send/load仍真version_conflict，历史读取不执行旧runtime，不改原snapshot/query/context/
  receipt或质量状态。disabled／撤权／copy／code/meta/依赖变化／extra file／假证／跨owner／
  source/PIT/hash失败仍拒绝；不把能力资格变化当作已获来源权限。

历史metadata场景仅模拟先前管理前缀；当前target来自实际Host受管解释器和六依赖指纹。
真实Store／snapshots／raw目录／Catalog发布事务／Dossier读取／授权逻辑均保留，不是假passed。
这不证明真实旧venv启动、供应商等价或模型质量。

首轮历史6 PASS；扩展历史＋relocation 31 PASS，152.49s。包含独立v1→v3、无receipt、mixed/
conflicting refs、source-only disabled、source撤权／raw改、正确self-digest伪owner及额外证字段、
依赖改、普通warehouse/query不借权、三参legacy／TypeError不降级、原Store全字节状态无写。
终态os.replace真故障注入保留原磁盘v1且无有效证，重启不宣称迁移成功。后续还加入raw期间
disable竞争，最终总检结果见receipt。

## Important 2：required metadata不能从receipt自己推导

真实A6 bundle＋`pack_native.run`复现成对删receipt/full metadata并正确重hash；先RED
22 FAIL／2原有拒绝PASS。新增独立 `research_pack_output_contracts_v1`，冻结到每个Native
version的references/output-contracts-v1.json并进入完整closure/hash。

严格receipt／full根／component必需字段、类型、schema/method version、digest、counts、
code_version、metrics/input_counts、refs、missing/rejected、parameters、limitations；拒绝额外
字段。方法metrics与限定语有独立固定表，event条件限定语／有限pack状态另检，参数投影从完整
封印独立重算，不将返回receipt当required oracle。原/展示两种回执hash／真实完整文件hash不混。
任何metadata溢出仍拒绝，64KiB／16MiB／128preview／50k等原预算不放宽。

39个输出合同检查PASS，0.26s：paired删root/component字段后正确重hash，full-only code/
counts/digest/source locator条件字段缺失、额外字段／类型／digest非法；20个合法冻结向量
同时作为正控制（旧risk coverage字符串两例原就拒绝，未改纯核）。真实writer／Native闭包另验。

## 回归／证据

近旧门100 PASS／1原Starlette warning，213.18s，含Dossier／保全、旧八场景和真实Native。
最终完整scope Python／JS／wheel／静态检查在
`logs/research-packs-b1-specfix-20261027-f631a2/`，由runner保存精确argv/env/PID/UID、duration、
日志sha、产物与自有opaque basetemp归档／清理事实。最终计数追加后才认证该候选局部通过。

Source-only与target请求都可因真实当前权限撤销而拒绝，历史等价证只处理受审能力版本策略，
从不补造first_observed/PIT/公开时点／完整市场覆盖，不重查源、不新增收费入口。当前真实
source子集仍仅BaoStock日线，其他数据缺口保留；真实LLM／MCP账户／供应商／UI／140／常驻
上线／CI／Windows/Linux本机／Mac Docker均NOT_RUN或后续root验收，局部绿色不等于正式报告质量。

## 资源归属

本波仅新 `rwb-b1-specfix-f631a2-*` argv明确basetemp与final runner随机根；不扫描／删除旧/tmp。
上一波50根创建证据已从本agent原始custom_tool_call逐条定位，含call_id／jsonl行／原始行sha；
1 opaque由actual PID75420 receipt证明，共50全匹配。proof SHA
`3315adbfc4354bdf6a21c83137cc77d057ea36335c73b69bbeb5151384df86b6`。
前次lsof实际`/usr/sbin/lsof -u 501 -Fpn`并接受0和1，不是误把1+empty当失败；非0/1具体退出
与stderr没持久化，稳定原因不能补造。目录在任何chmod/delete前保护退出。旧50根只交root复核
当前UID/dev/inode/openfiles后按既有授权处置；本worker不新删，不动真实服务／数据／他任务资源。

## 最终局部结果

完整本波Python闭包 **369 passed、16 subtests passed、1原Starlette/anyio warning**，462.79s；
runner PID84163、pytest PID84165、UID501；实际runner计时463.078s，exit0。涵盖原249范围、
新历史/输出合同/多hop/事务故障及Dossier邻近门。日志SHA256
`2d023b29a6829a666fdcc4a2ffa4004ae4826891dd119d48e173c31243d4f27e`，receipt SHA256
`31fc7ac3308eb266eb88d86e0445443697759acb49837f9047882c73b5b74661`。
原37个近JS全PASS／135.89ms。实际新wheel随该闭包执行installed-like读取，包内schema／lock／
纯核资源加载不依赖checkout；无需新依赖或改安装器／lock／CI。完整argv/env在final receipt。

最终opaque temp中48份Native／结果fixture先归档并重读SHA核对后，由原runner按UID/目录
检查清理，temp_cleaned=true。本波早先explicit basetemp和日志仅保留证据待root收尾，不混入
旧50根、不自行扫描删除/tmp。Mypy仍因既有缓存缺librt未执行，未安装。真实供应商／模型／
生产网络／UI／140／跨平台／CI／常驻服务仍NOT_RUN。局部绿是复SPEC／Python／TS评审的候选，
不代表九包来源完整、正式报告质量或整个计划完成。
