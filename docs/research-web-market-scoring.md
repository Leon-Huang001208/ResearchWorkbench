# 市场六维评分与事件修正

首批只读证据可展示三地主指数可复算的原值及具体缺口；不能代替原六维合格运行或开启生产总分。

本模块是 Host 内的确定性研究计算，不创建研究引擎、自动下单或生产评分。解释性研究继续交给 DSH。现有 `market_analysis.py` 的描述性读数与境内 ETF 工程模拟不因本模块获得正式准入。

## 固定范围和规则

- 目录固定为 SSE、CSI300、CHINEXT、SP500、NASDAQ、DJI、HSI、HSCEI、HSTECH；预测期限固定为未来20个本市场交易日。
- 规则版本为 `market-six-axis-v1`。六维输出统一为0–100，但市场原始指标、覆盖范围和数据源不同，不能据此给三地排名。
- 每个配置固定指标、方向、来源目录、市场或指数范围、归一化窗口1260条和最少252条过去观测。来源在目录中只表示候选，不等于许可、健康或历史时点资格。
- 趋势使用20日动量，广度使用明确范围的上涨占比。A股情绪沿用已确认涨跌停余额、资金沿用来源声明的全市场主力净额、估值使用正PE样本中位数；风险使用20日波动的反向历史分位。
- 美股及港股情绪使用本市场期权成交量 put/call 比的反向分位；资金使用明确追踪范围的ETF初级市场净申赎／资产规模；估值使用指数正PE。不得把成交量／成交额叫作资金净流入，不把A股涨跌停规则套到海外。
- 广度占比直接乘100，A股涨跌停余额由[-1,1]映射到[0,100]；其他指标使用过去观测的中位秩分位，估值、风险和put/call取反。历史当日、未来获知和冲突修订不能参与归一化；日期以本市场时区判断。
- 六维同日、同范围且全部有资格才能计算算术平均。缺失项不填0或50，不重配权重。
- 通过独立验证的事件家族每项±1分，同家族只计一次；同家族方向冲突时贡献0，合计截断在±5分，最终研究分截断在0–100。无合格基础分时事件因子贡献为0且总分不可用。

## 证据和准入

每项观测必须绑定原件引用与哈希、提供方、指标名、原生单位、明确范围、原始观察／公开／获知／失效时间。归一化历史的单位必须与固定指标一致；百分数、比例、币种、倍数不混用。当前源验证器还必须提供绑定完整观测哈希的授权版本和历史时点证明回执。调用方自行填写 `pit_verified` 或 `approved` 不授予权限。

`ScoreService.register_inputs()` 只供可信 Host 来源适配器调用，没有上传原始评分或观测的HTTP入口。它将原件引用、完整分项和序列冻结到个人 `factor_inputs` 不可变记录，并覆盖调用方提供的来源回执。没有安装可信来源验证器或缺乏历史证据时仍保留配置和缺口，不造合格数据。

正式研究验证从 `study_run` 记录读取。服务重新核验规范化验证报告的 `report_digest`，要求 `VALIDATED`、角色、指数、期限、配置与信号规则／执行协议／代理身份／来源合同摘要、独立 holdout 身份及有效时间均匹配。训练／测试集摘要单独保留审计，不要求它等于今天的新行情输入摘要。今天和明天的新输入分别重验来源、PIT和单位，可在相同规则身份下使用同一有效的历史验证。历史截止时间不能让已经失效的报告重新变成当前合格。旧运行的原结果保持不变，读取时另给出当前资格；撤权、原件损坏、配置变动和过期会令当前结果不可用。

HTTP服务读取VALIDATED证书时，另以研究服务的同一动态实现摘要核对`implementation_digest`；
缺失、变更或当前实现不可读取均拒绝正式评分消费。历史运行也重新验证当前资格，不能仅凭
旧report_digest正确就使已变更算法继续获得准入。纯计算函数不提供这一服务端信任入口。

事件及日历修正另需实际适用窗口。可信 Host 的 `resolve_market_overlay_context(study_id,spec,report,index_id,as_of)` 返回严格 `OverlayContext`，包含已核验 Calendar、事件／节假日、来源引用、版本与资格回执，不包含 `active` 布尔值。服务核对当前事件修订、确认状态与原件，再按冻结的单一窗口规则重算起止时刻；未来日程必须有当时已公开的日历边界和事件证据。修正只在 `[窗口起点收盘,窗口终点收盘或复市开盘)` 内有效，报告的一年有效期不等于全年激活。响应保留实际采用的窗口、来源版本、上下文摘要和事件修订。

基础策略身份由可信 Host 的 `resolve_market_scoring_context(index_id,as_of,inputs)` 返回 `ScoreContext` 中的真实 Proxy、来源合同及回执推导。上下文必须绑定当前指数／时点，代理及适用交易规则必须已知且已生效。任何上下文缺失、旧时点重放或原件变化均拒绝正式研究分／修正；浏览器不能提供这些上下文。

通过历史验证也不等于生产激活。HTTP响应将合格历史研究分放在 `research_score`，`total_score`、`effective_score`、`allocation` 保持空，`formal_score_enabled` 和 `production_enabled` 为false。生产激活需要另一项明确授权与受审合同，本版本不提供该入口。

## HTTP与内部接口

所有接口均由当前账号 ResearchService 选择个人事件元数据和原件归属。

| 接口 | 行为 |
| --- | --- |
| `GET /api/research/market-scores` | 指定指数的安全预览；无证据时返回具体缺口，不初始化数据库 |
| `GET /api/research/market-scores/profiles` | 九指数、三市场及六维固定配置 |
| `POST /api/research/market-scores/runs` | 只接收 `index_id/as_of/inputs_id/validation_id/overlay_ids/idempotency_key`；由记录ID解析全部证据 |
| `GET /api/research/market-scores/runs` | 历史运行分页，明确为历史结果 |
| `GET /api/research/market-scores/runs/{id}` | 冻结结果和重新核验的 `current_eligibility` |

写入沿宿主的同源、账号及显式用户操作规则。未知请求字段拒绝。幂等回执绑定稳定请求而不是计算时钟；同键不同请求返回冲突。重放原请求保留旧记录，同时重新核对当前资格。

内部 `compute_score()` 接收可信来源回执，执行纯计算；`study_signals()` 编译冻结序列的候选分供策略验证，始终标为 `candidate_only`。两者本身不能安装授权、接受浏览器分数、开启生产模式或证明市场预测有效。

## 验证与实际状态

`tests/research_web/test_market_scoring.py` 使用合成来源、合成历史和合成验证报告检查：等权、缺轴、跨市场指标、时区／未来数据、冲突历史、来源哈希与权限、验证绑定、家族去重及贡献上限。成功夹具只证明规则实现，不是任何真实市场的准入证据。

真实免费源覆盖、独立样本外有效性、模型、生产部署、生产评分与真实交易分别验收。未取得的证据保持未执行或不足，不由配置存在、HTTP成功或测试数量替代。

## 实际 Host 原生输入适配

`EventInputHost` 是默认的实际来源解析器，不依赖测试回调才能读到数据。它只读取当前账号已经登记的 DataHub dataset、私有原件及事件记录；构造时不读文件、不取凭据、不发网络请求。入口在工作线程内持有 `activity()`，断开HTTP不会提前释放仍在运行的资格检查。

原生登记只接收 `kind/session_id/dataset_id/index_id` 与已有不可变记录引用；`choices()` 只返回最新100条ID、版本和标签，不回传行情历史或凭据。`link_bundle(bundle_ref,links,key)` 校验指数、交易所、代理价格身份和因子代理对应关系，经CAS创建价格输入新版本；旧研究的原版本不变。

可信来源生产器须在 DataHub manifest 的 `provider_metadata.event_input_schema` 明确声明下列合同。声明只选择解析器，不授予PIT资格：

| 合同 | `rows.json` 形状 |
| --- | --- |
| `rwb-event-calendar-v1` | 单行 `{"calendar": Calendar, "holidays": [...]}`；必须有实际逐日开收盘、半日市与明确时区 |
| `rwb-event-proxy-v1` | 单行 `{"proxy": Proxy}`；包括真实追踪身份、上市日、单位、带来源的历史税费／交易单位／结算规则 |
| `rwb-event-factors-v1` | 单行 `{"factor_bundle": {index_id,profile_version,series:[{as_of,axes}]}}`；每个指标和历史值保留单位，manifest `fields[metric].unit` 必须与固定配置一致 |
| `rwb-event-prices-v1` | 逐日 `{index_id,role,asset,unit,day,open,close,split?,dividend?}`；指数单位为 `index_points`，代理为 `<currency>/share`，代理必须有实际公司行动资料 |

长历史因子另支持同一 `rwb-event-factors-v1` 下的紧凑 `factor_bundle.format=factor-matrix-v1`：`columns` 只保存一次各轴的指标／单位／范围，`rows` 每日保存 `as_of/observed_at/values`。个人输入表只保存原件引用、配置摘要、真实覆盖范围及 `latest_as_of`，不重复持久化每天252–1260条归一化历史。Host 按实际 canonical Fact 的逐日可得时间流式重建过去窗口；当前点只在内存中展开一次供同一评分公式复算。最初252条归一化预热不生成分数，后续缺口不填现金或中性分；回测排除预热前缀并保留独立指数研究范围。15年实际 Snapshot／RecordStore／WarehouseBridge 合成回归验证真实大小限制及流式结果与展开计算一致，不放大8／16MiB限制。

日历捕获时间只作审计，不覆盖逐会话公告时间；多年度日历必须匹配每个会话的 canonical 日期或公告版本。代理身份与各段税费／交易规则分别匹配自己的可得时间，找不到相应事实就拒绝，不取全批次最大值或猜测更早发布时间。合并来源生产器可使用 `identity_announcement_version_ref` 和按生效日映射的 `rule_announcement_version_refs` 绑定实际 canonical 版本。

原生日历的`holidays`在历史研究和当前修正中共用同一投影。每项须有明确日期、known_at与
公告版本（可继承整段公告），正式历史还要求同版本canonical calendar Fact.value的
`{sessions:[...], holidays:[...]}`实际包含完整同一假期原项；仅render附加的普通周末拒绝。
获知时间取声明和匹配事实available_at的较晚值，当前相关假期迟到／未知或两来源均无假期证据
会返回明确缺口。已确认timeline日历候选仍可沿原路径使用，不能据缺项静默声称不在窗口。

主研究输入必须是目录中的价格指数，不能把代理ETF当作独立指数证据，也不能将同一来源引用同时用于两者。代理逐日状态必须明确，`suspended` 保留到实际重放；未知状态不能当成开市。原始价格依据必须由实际查询或 canonical dataset 的 `adjustment=none/unadjusted` 证明，调整后／总回报数据不能仅靠代理声明再次施加分红与拆股。

来源引用、提供方、获知时间和回执由 Host 从原件重建。原始数据的 `approved/pit_verified/historical_eligible` 等布尔字段不授予权限。普通快照的获知时间不得早于实际私有 manifest 的取得时间；转存事件归档不会把旧日期变成当时已知。

正式历史资格另要求读取并校验私有 `market-store-frozen-v1` 原件，再通过现有 canonical `WarehouseBridge` 以同一 `purpose=backtest/as_of` 查询重新核验实际存储、owner、授权、单位与冻结摘要。Provider-native snapshot 的既有拒绝门不变；只补字段、修改metadata或复制PIT布尔值不能通过。历史不齐时仍可保留描述性统计和具体缺口。

来源授权或配置变化、原件损坏、单位冲突、迟到获知均拒绝资格。恢复到未知历史根时，`.event-qualification-reconciliation-required` 单调栅栏阻断所有资格回执与当前评分／窗口上下文；没有浏览器解除入口。来源不产出上述明确原生合同、缺真实日历时刻或缺历史证据时保持不可用，不把仅有交易日的标准时刻投影升级成真机／PIT证据。
