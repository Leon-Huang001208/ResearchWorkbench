# C3/C4 自有方法动作切片

宿主：Mac mini / macOS；任务：Web 功能开发。工作区基线
`397365b1c565636eb1b8c9955efecad5d18d627d`，沿主任务已启动 Harness，不重复初始化。

已实现三份 `kind=skill` 版本化方法包、冻结 stdlib 原件动作、严格 query/limit 与问题预置适配。
没有增加模型循环、引擎、供应商调用、依赖、秘密、部署或 schema 数据库迁移。

RED：新增参数测试先因模块缺失失败，证据 `/tmp/rwb-c3-actions-3V1xlNQt/red.log`。
首轮 GREEN：参数/原件 32 tests PASS，Catalog/冻结脚本 3 tests PASS，证据同目录
`green.log`、`packages.log`。该目录已登记 owner.json。
后续当前纯模块目标集 `target3.log`：43 tests PASS；Ruff、Black、isort 对本切片 Python 文件通过。
实际重开三份已有官方摘录的原 SHA（MSFT income/cashflows、FOMC September），不等于新抓取、完整文档
或 live 来源证明。未执行 mypy（现成环境 librt 不可用），不安装依赖补门。

## 当前集成切片

主任务已批准并实现固定三 CID 的 `method_execution={capability_id,version,context_sha256}`。
三份独立 owned-method 场景沿原 prepare/handoff/send/选材链运行，原八合同字节不变；来源选择使用
固定 registry 区分旧两 pack 与三方法，不产生伪 pack_seal、pack 资格或执行记录。

`scenario_method_sources.py` 从当前授权原件冻结 inputs/methods 私有副本，Host 固定 launcher、
真实 Native supervisor 与原私有桥 `kind=owned-method` 完成后，Host 重新授权、核文件身份、重读
原件与 ledger，并用已验证与冻结资源同字节的固定函数复算，再写原 receipts/index.json 的
method_executions.saved。普通 code 不能读内部原件或写 method-results，不能自造 ran。

私有输入明确由现 HTTP file、Dossier file 与 Claw reference 三入口按 path.parts[:2] 固定拒绝，
包括旧缓存 ID、.txt 半文件、撤权和回执缺损，不以扩展名当唯一边界。原 page-evidence、普通上传及
来源引用仍进入旧强核。仅已登记 scope.file_bindings 的生成副本从数字观察投影排除；未登记文件
仍可使真实 quality 返回 invalid。取消/未知不保存为成功，也不能换 callId 重跑。

## 实际验证

- `integration-final.log`：53 tests PASS。三方法各实际 source capture/read→固定 DSH SkillProvider/
  ToolRuntime/guard→原 sandbox→私有 completion→Host复算→原 report_plan/canonical/HTML/DOCX→
  research_check_quality。正例真实状态均 incomplete；公司原表 245122/211915 经系统计算为15.67，
  测试叙事为 scripted fixture，不是真实模型。覆盖取消、不可重试、完整性、普通 code 禁读写、
  receipt 丢失、撤权、半文件、未知输入触发 invalid。
- `regression-final.log`：25 tests 已通过后，旧 stage2 总 Skill 数30断言失败。前三十之外，397基线
  已有九 pack（实际39），本候选再加三方法为42。stage2/3/4 仅更新显式42与九 pack/三方法集合，
  六/七/五个旧算法的 disabled、receipt、selection 拒绝保持；不是新方法等价通过旧阶段。
- `gates-final.log`：修目录计数后，三阶段18禁用门与原零分母剩余目标共5 tests PASS。前25包含
  原八场景、原两pack实际 Native（含取消）、weekly 权限与普通 sandbox；不重复执行已过25项。
- `source-picker-js.log`：20 tests PASS，包含固定 owned flag、旧两pack、来源预览/冻结及 unknown。
  Ruff、Black、isort 对26个本切片 Python 文件 PASS，五个改动 JS 文件/Native helper 的 node --check PASS。
  mypy NOT_RUN（主任务已记录现成环境 librt 缺口），没有安装依赖。
- DataHub 财务正例使用实际 Sina HTTP MockTransport→原 provider parser→真实 snapshot manifest/query/rows：
  600600.SH、2026-06-30 与 CNY 保留，单位与累计 basis 未知保持 partial。没有 mock DataHub.query 或
  假造单位；也没有声称执行了真实供应商请求。

## 尚未实现的代码集成

1. C2 去重制品尚未绑定，新闻/调研明确 source_version_dedup_not_run；属于 CODE integration pending。
2. C4 仅严格纯参数函数，未接实际兼容工具入口；C1 全部相应参数仍 unsupported/pending，没有 mapped。
3. 原 report_plan percent_change 尚无 owned 方法对非正基数的独立准入硬门。现正基数示例与零分母
   回归不覆盖负基数；禁止升级为完整财务方法或正式映射。不改通用数学，下一窄集成处理。
4. 现 annual 解析器不认证实体/URI/通用币种。MSFT fixture 的 numeric/report_plan 链可跑，但来源动作
   保留 unclassified/financials 缺口，没有新增 MSFT URL 专用分类。非 UTF-8/PDF reader 自动接入未实现。

真实模型、外部来源网络、正式研究接受、部署与其他平台 NOT_RUN；当前候选不是整个 T3 完成。

## 本轮测试资源收尾

只归档并回收本轮登记的 `/tmp/rwb-c3-actions-3V1xlNQt` 下19个 pytest 子目录。510份必要原件、
Store index/执行回执、canonical/格式/ledger 与日志进入 `evidence/run-evidence.tar.gz`（2,369,573 bytes），
SHA-256 `721d4377e10f3193b97a3f0704b55c9e81760bcb5b3839237243a82445ebe14c`。
全部41,002,652原始字节逐文件恢复后按 manifest SHA-256 读回通过，详见
`evidence/retirement.json`。初次清理遇只读测试包目录失败，
仅给本轮已验证退休目录恢复 owner 写位后重试成功，回执 status=cleaned。未改任何服务、全局配置、
其他任务、Docker 或工作树。测试根1.7 GiB降为4.0 MiB，磁盘可用由5.9 GiB回到7.7 GiB。

模块合同与边界见 `docs/research-web-owned-methods.md`。独立 SPEC/QUALITY、完整 Router、
本地 CI、Mac 干净安装及发布交由主任务聚合，不由本切片自评替代。

## Python QUALITY 准备原子性修复

独立评审基7338仅发现准备阶段先写副本后检查资源/预算的问题；原SPEC与JS评审已通过，不以这些
评审代替本轮Python复评。仅修改owned来源模块、相关新测试、模块文档、报告与生成Python索引。

RED：`/tmp/rwb-method-atomic-62DCRqRZ/red.log` 在7338实际重现 `_file` 资源拒绝后私有副本残留。
修复将全部可预检资源/闭包、源身份、数量、总字节（含上下文/资源）、runtime和launcher上界移到写入前。
小准备事务记录本次exclusive出生的parent/dev/inode；只有身份一致的自有文件和自建空目录可以回滚。
已有/复用、替换文件及替换父目录一律保留，不清未知，不伪造saved/started掩盖orphan。

Store save异常通过原index读回判别：同一receipt明确没有新ID且原列表一致，才恢复内存旧列表并回滚；
新ID已提交则保留真实durable prepare intent（没有native_result），无法确认也保留未知并拒绝重复调用。
没有增加回执schema、恢复器、公开接口或新执行通道；普通来源/alias/Native与质量权限门均未放宽。

GREEN：`final2.log` 11 tests PASS（57.75s）：实际资源拒绝、真实源与资源字节sum的限额-1/精确限额边界、
write/fdopen/readback/save-before故障及显式重试、已有文件保护、文件/父inode替换保护、save-after真实
原子发布后的未知不可重试。首轮8通过；补测首轮仅测试把已有directory包装的StoreError误认OSError，
改为核验实际异常及cause，未放松产品拒绝。没有运行模型、来源child、供应商网络或安装依赖。

原7338的53/25与真实Native链没有机械重跑：`unchanged-abi.json`逐函数AST比较确认 launcher、_file、
source_context、_resources、_readback、complete_execution、quality_issues、validate_storage、
original_evidence_files 九函数不变；Native JS、sandbox、固定Skill资源/入口、权限和报告实现未改。
这仅说明可复用证据范围，不把旧SHA执行伪写成本候选执行。C2/C4/非正基数三个CODE pending保持。

本轮两文件 Ruff/Black/isort 与生成Python索引 --check PASS，diff --check PASS。新证据根独立登记
`/tmp/rwb-method-atomic-62DCRqRZ/owner.json`，未使用共享pytest根，也未写入独立评审的保护证据根。
243份必要原件/index/故障回执与日志、共2,642,106原始字节逐项恢复核SHA-256通过后，保存为
`evidence/preparation-evidence.tar.gz`（427,937 bytes，SHA-256
`7a7d0e1d7e52e0b449dfb3f53b5b50ae8e036042bdd6cda19a49db7fb30d99eb`）。
仅回收本轮四个登记pytest子目录，retirement.json status=cleaned，测试根从1.0 GiB降为1.2 MiB。

## C3b/C4实际完成接点（基线b84020549f5c8e23253aabba7474b6cdfbb7421b）

宿主macOS，Web功能开发，沿既有Harness与本任务独立worktree；无push/PR/merge、真实来源网络、
供应商、模型、收费、秘密配置、依赖安装、部署、正式数据库或系统配置操作。

1. 两owned场景显式timezone cutoff_at沿原输入冻结；严格上海日期一致，不从日期/当前时刻补值。
   Host当前resolve_reference→原project_source_version→公共execute_atom_bundle执行deduplicate_source_versions
   1.1.0，保存原receipt与完整canonical full_result字节。调用前canonical roundtrip稳定原legacy digest
   的对象顺序，不改C2算法/record schema。新wrapper绑定core/dependency/projector、完整SourceSet、
   owner/target/原hash/locator/发表与取得时间、输入digest和gaps，纳入原file_bindings/context hash/
   16MiB合计和b840准备原子事务。Native只消费Host固定声明的c2-dedup.bound；Host completion/quality
   重新授权、同投影、同atom复算。身份明确Host执行C2、Native消费。缺cutoff/unsupported/future/
   unknownrole/pub/上游完整性缺口保留，不冒充运行原source pack。
2. 公司Host-only policy owned-company-positive-base-v1由原handoff/冻结contract三元绑定重建；SDK和
   Host report_projection各传入原recipe与Summary实际resolved operands。非正基数硬拒，Summary
   derived/$step/abs基数拒绝；owned公司canonical必须system_plan，删policy/手写canonical不能绕过。
   245122/211915仍15.67，generic负基数原-300.00不变，difference必须显式选择。
3. 固定RWB wrapper rwb_query_latest_cls_news仅query/strict int limit=1..100；原datahub_search_news
   日期/通用schema不变。原private business-query新增严格owned union，实际adapt_query_news→真实
   DataHub.query/broker/CLS parser/snapshot/cancel；sourcecls、research、strict、allow_fallbackFalse固定。
   wrapper自身目录只在Host本地CLSready及scope允许时可见，拒绝只掩蔽该wrapper，实际调用重复准入。
   wrapper-only required_tools记录原datahub_search_news，不把CLS加成三原件方法强制依赖。
   三question preset在owned prepare/create_handoff/source-selection同helper执行，Host先核当前选择，
   冻结question后沿原handoff/send/Native方法/report/quality；冲突明确拒绝，不解析ticker取数、不改旧任务。
   C1仅4个实接入口的5参数标native_subset；supplier alias仍拒，其他参数/旧18gate不放宽。

证据根 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-c3b-completion-ozn6fz5b`，每轮显式basetemp，
owner登记task/slice/UID/PID/dev/inode/argv/candidate。首RED因dedup模块缺失失败；cutoff目标1PASS。
native1原atom原receipt对照暴露对象顺序依赖，native2随后被原sandbox exactfilename门拒绝；修后native3
两C2真实纵向PASS。未绕路径门，仅获准把固定c2-dedup.bound加入原METHOD_INPUT_POLICY两处regex。

实际验证：

- target.log：34 PASS/78.89s。C2未来取得、unsupported、完整SourceSet/版本/inputdigest变造；公司负零、
  Summary direct/$step/abs、SDK删policy与手写canonical经真实Host quality invalid(report_invalid)；
  wrapper严格Host参数、scope/CLS disabled、真实provider取消不落snapshot、C1原alias全拒。
- presets.log：6 PASS/50.74s。原三方法及3preset各真实capture/Hostfreeze/handoff/send/pinned Skill/
  ToolRuntime/guard/Native sandbox/completion/原report_plan/canonical/HTML/DOCX/research_check_quality。
  final-native.log再复验六正例通过；新增负基数例产品已正确runner failed/exit1，首轮测试误认transport
  isError，改按runnerstatus/stdout断言，final-neg.log 1PASS/8.26s，稳定owned错误且无canonical。
- compat2.log：1PASS/5.23s。真实Native wrapper→Hostadapter→DataHub.query→MockTransport真实CLS
  parser/snapshot；row_count[0,1,2]、真实rn[1,2,2]，验证limit先行/casefold/空query及原日期schema。
- ui-guard.log：50 PASS，原picker、owned cutoff/preset冲突/切换无泄漏，wrapper目录mask恢复/撤销。
- static.log：20个改动Python Ruff/Black/isort PASS；生成Python索引--check、改动JS/helper node--check、
  diff--check PASS。mypy NOT_RUN（现成librt缺失，不安装）。完整changedset文档/API Atlas/Router/CI/
  Mac干净安装与独立SPEC/Python/TS QUALITY由主任务继续，未以此自评替代。

真实quality正例仍incomplete，负基数未生成canonical保持incomplete/report_missing；叙事为scripted fixture，
HTTP仅离线输送边界，真实模型/来源网络/正式报告接受/部署/他平台均NOT_RUN。本切片不等于整个T3完成，
T4/T5及其后续门保留。
