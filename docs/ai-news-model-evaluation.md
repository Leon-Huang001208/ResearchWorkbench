# AI News 自主引擎模型对照准备

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](research-web-ai-news.md)。

本流程固定原始 AIHOT `26d436497d9ddba9e7dd88eed255cfe0105ce368`，只准备云端与本地模型的相同输入，不运行推理。工具使用 Python 3.12 标准库；无安装步骤，无 API Key，无模型请求。任务属于 macOS 功能开发的离线评估准备，不构成 Windows/Linux 或产品质量验收。

## 可复现命令

从仓库根目录运行，替换两个目录为本次独立的新目录：

```bash
python3 scripts/ai_news_eval.py prepare --output evals/ai_news/session --raw logs/ai-news-eval/session
python3 scripts/ai_news_eval.py freeze --output evals/ai_news/session --raw logs/ai-news-eval/session
python3 scripts/ai_news_eval.py template --output evals/ai_news/session --raw logs/ai-news-eval/session
python3 scripts/ai_news_eval.py validate --output evals/ai_news/session --raw logs/ai-news-eval/session
python3 scripts/ai_news_eval.py balance --output evals/ai_news/bilingual-session --raw logs/ai-news-eval/bilingual-session --base-output evals/ai_news/session --base-raw logs/ai-news-eval/session --chinese-sources evals/ai_news/supplemental-chinese.json
python3 scripts/ai_news_eval.py template --output evals/ai_news/bilingual-session --raw logs/ai-news-eval/bilingual-session
python3 scripts/ai_news_eval.py validate --output evals/ai_news/bilingual-session --raw logs/ai-news-eval/bilingual-session
python3 scripts/ai_news_eval.py reference --output evals/ai_news/reference-session --raw logs/ai-news-eval/corpus-bilingual-20261017 --base-output evals/ai_news/corpus-balanced-20261017 --reference-spec evals/ai_news/reference-spec.json
python3 scripts/ai_news_eval.py validate --output evals/ai_news/reference-session --raw logs/ai-news-eval/corpus-bilingual-20261017
python3 -m unittest discover -s tests/research_web -p test_ai_news_eval.py
```

`prepare` 获取固定提交的 `industry/sources.json`；`freeze` 对目录内公开 RSS/Atom 逐轮选取链接，最多每源12条，最多50篇正文响应。每请求12秒、每响应2MiB，匿名 GET，不携带Cookie、认证或API Key，拒绝私网、查询参数、AIHOT站点、X/微信/Jina。日志使用 `research_workbench.ai_news_eval` 标准 logging 层及 `logs/ai-news-eval/preparation.log`，避免引入项目settings的第三方依赖。网络失败保留异常类型与URL，不假造缺失数据。不可重复覆盖冻结目录；重新采集使用新目录。冻结进行中中断的目录须保留，另开会话重试。

完整原始响应与派生正文仅存本地 `logs/ai-news-eval/`，不加入Git或公开全文。Git内清单保留原始URL、最终URL、获取时间、媒体类型、长度、SHA-256、来源ID与划分；`plan.json`不含原始文章。页面可能包含导航、脚本或付费墙，HTTP成功不证明正文完整或可用，所有输入必须人工核查。初版输入为原始HTML；`balance`形成新的双语版本，使用固定`stdlib-htmlparser-v1`抽取正文，跳过script/style/nav/header/footer，优先article/main或post-content/entry-content/article-content类，缺失时使用明确标记的body_fallback。冻结派生UTF-8正文的实际字节、长度、SHA及抽取器版本，云端/本地模板绑定同一份正文输入SHA并保留原始HTML SHA。`validate`从原始HTML重算正文及统计，不能只靠修改清单宣称分层完成。

补充中文来源清单 `supplemental-chinese.json` 引用官方Qwen中文RSS冻结件；运行`balance`前，该清单指定的 `feed_raw_root` 下必须有对应原件且SHA正确。本文所附本地语料已保存原件；从新设备复现时可匿名下载清单中的原始URL，再核对长度与SHA，若上游RSS已变化则保留缺失状态或使用经哈希校验的原件归档。中文文章的发布日期来自冻结RSS的pubDate，与实际抓取时间分别记录；不声称这些2025年发布是今日新闻。旧英文源发布日期未抽取时保留null。

## 样本与人工标注

目标50篇；不足则 `INCOMPLETE`。初版使用每第5篇holdout；当前参考版按`reference-spec.json`声明的事件组固定40 tuning/10 holdout。Qwen3家族、中英Qwen-Image及Edit、Beam、Meta条款、GitHub分类器、Muse Spark及Google Research@专题/综述分别保守归组，组内不得跨split；关系对也不得跨split。已知分组可复验，但未完成人工完整事件排查前不得认证完全没有语义泄漏。调整划分必须新版本重新冻结，不能修改既有结果绑定。

`template`只生成空模板，不能充当参考标注。`reference`根据已阅读正文的显式字面锚点生成50篇具体提案：每篇有命名主体实体、来源声称的事件、至少一条事实锚点及冻结正文UTF-8字节span和SHA；事实归因标为`source_reported_claim_not_independently_verified`。关系20对经明确选样，14 tuning/6 holdout，包含3个`SAME_OCCURRENCE`、3个`SAME_STORY`、14个`UNRELATED`，每对有具体理由、原始HTML摘录span及正文事实引用。所有值均为`proposed_reference`、`needs_review`，`gold_approved=false`，审核人仍为空，不能当作独立人工gold。

语义遵循固定上游`group-definitions.md`：同一官方Qwen3/Qwen-Image发布的中英原文及Meta同次条款报道属于同次发生；RTX Spark发布→实测、Beam发布→AWS接入及具有companion链接的GitHub分类器后续解读作为同一故事不同进展提案。Qwen3→Guard/Embedding/MT虽有架构承接，属于不同产品独立发布，原定义要求`UNRELATED`，不能偷换成follow-up。ROUNDUP当前未覆盖，后续扩展须新版本。提案需独立双人标注、分歧裁决、补齐事件时间/多事实及摘要事实性，禁止模型自评充当人工gold。完成tuning后锁定prompt，再揭盲holdout，不能用holdout调参。

当前对照入口为 `evals/ai_news/corpus-reference-20261017`，原始文件与正文在 `logs/ai-news-eval/corpus-bilingual-20261017`。在双语版基础上用两篇真实Qwen英文同篇原文替换两篇独立报道，仍50篇、保留10篇官方中文及至少30篇确认英文、9篇语言未确认。另1篇Qwen-Image英文原文含中文渲染示例，v1 CJK规则将其计入中文，因此机器计数为zh11/en30，不应宣称11篇纯中文。44篇满足“指定正文容器可见文本不少于3000 Unicode字符”操作定义，满足10中文/15英文/10长文的数量门。英文替换原件的URL、实际获取时间、SHA和替换对象保存在reference-spec中；未抽取的英文发布日期保留null。初版失败记录继续保留，不为补齐计数虚构来源。正文完整性、语义分层及主题平衡仍待独立审核，中文集中Qwen，不能代表整个中文新闻生态。

## 24GB Mac 本地可行性计划

这里只记录将来验收方式，不认证可运行模型或吞吐。24GB统一内存还须容纳macOS、既有常驻服务、推理runtime、KV cache及峰值工作区；模型权重文件大小不能代表总内存。未来获得推理授权后，先选择小规模量化候选与短上下文做单并发准入，记录精确权重/量化SHA、加载峰值、推理峰值、上下文长度、交换使用和错误；只有保留系统/常驻服务余量后再逐级扩大。云端与本地比较使用相同冻结正文、同一任务prompt及输出schema，分别记录模型能力差异与运行配置。上下文超限不得静默截断；应保留失败或另建版本，记录截断/分块规则与派生输入字节。当前所有候选的内存可行性、质量、速度、费用均 `NOT_RUN`；不得把参数规模或量化名称当作质量排序。

## 将来运行的硬门

`run-template.json`的cloud/local质量、时延、费用、tokens仍全为null，`NOT_RUN`，评分`MANUAL_REQUIRED`。配置模板`evals/ai_news/run-config-template.json`故意保留模型/revision/量化/价格等null且预算为0，不能直接执行。未来独立授权后填写精确模型ID/revision、权重SHA（本地）、量化、runtime、硬件、定价日期和预算；元数据来自操作者，不是本工具已探测验证的模型身份。

`request`是默认dry-run的单任务请求构造器，不连接模型或DNS。支持固定pin真实文件名`prefilter`、`understand`、`selection-score`、`summarize-article`、`translate-body`、`group-pair`、`story-digest`；核对原版prompt/partial全部SHA，填充固定site身份及时间/来源/正文变量，拒绝未填变量。生成精确prompt/输入/model/quant/runtime/预算及脚本SHA绑定和标准OpenAI-compatible `chat/completions`请求体，云端与本地共享构造流程。prepare与execute都核对唯一split；execute还重验实际corpus/raw、每个输入身份及真实split，不能只改request标签混用tuning/holdout。所有正文与请求只写私有logs，不提交或公开。

单篇任务均接受1篇；pair与digest限2篇、必须同split，超出范围明确拒绝。prefilter使用原`JSON.stringify(renderContext)`标量字符串；understand使用原单篇材料前导与来源/标题/正文/材料质量字段；selection-score只使用原时间/标题/完整正文段落，不混入来源加分依据；group-pair明确渲染报道A/B与原文证据段落。translate-body传`{segments:[完整正文逐行HTML转义段落]}`，不截成摘要，响应`t`数量或任一段缺失都会进入UNKNOWN；它只覆盖冻结可见正文，不证明原页面链接/图片/代码DOM被完整保真，生产HTML翻译仍须原runtime验收。story-digest按原事件标题、时间顺序报道和fact evidence字段构造，消费有字面出处的参考提案事实；仅允许清单中明确同事件/进展的pair且两篇均有来源发布时间，未知日期、缺事实或不相关对明确unsupported，不伪造日期/动作/对象，也不把原始文章JSON直接喂错prompt。当前可用的真实例子为Qwen3中英文同篇，另一方日期来自冻结HTML的article:published_time。

```bash
python3 scripts/ai_news_eval.py request --output evals/ai_news/corpus-reference-20261017 --raw logs/ai-news-eval/corpus-bilingual-20261017 --config logs/ai-news-eval/operator-config.json --article-id article-zh-010 --prompt understand --request-file logs/ai-news-eval/request.json
```

真实执行是独立后续任务，必须显式`execute --allow-network`并提供独立授权文件、私有receipt位置。授权文件须包含`permission=APPROVED`、明确`approval_id`、`scope=ai-news-model-eval-single-request`、请求文件精确SHA、有效期、`max_requests=1`、输入字节/输出token/美元上限；本阶段没有生成任何真实授权。云端只解析一次并验证所有答复为公网，socket直接连接已验数值地址，TLS保留原hostname的SNI与默认CA证书/hostname校验，防止第二次DNS解析重绑定到私网；不使用代理、不跟随HTTP重定向。API key只从配置的环境变量在发送前读取；本地仅显式loopback HTTP端点。推理transport默认None，授权缺失或未注入transport直接拒绝。独立持久ledger按请求SHA先fsync登记再发送，换receipt文件名也不能重试；timeout、未知模型、缺usage、非正常结束或超预算均保留`UNKNOWN_DO_NOT_RETRY`，原始响应先落盘再确认结果。完成receipt只说明请求/usage可核对，质量仍`NOT_SCORED`，不修改任何模型质量空指标。

费用保留以消息UTF-8字节数+1024作保守输入token reservation，再结合操作者提供的当日价格和最大输出token；不是独立tokenizer或厂商账单上限证明。必须另核对厂商价格、服务侧预算/硬限额及真实权重/runtime，不能把本阶段fake transport合同测试视为真实计费或推理验收。本阶段仅fake transport，无推理HTTP调用。

构造器为`standalone_full_text_microtask_v1`：使用原prompt文本，保留完整冻结正文；摘要任务将正文作为原prompt变量，并在标准user数据消息中重复绑定一次，明确计入预算。它没有复刻原引擎6000字符清洗/截断、身份装配、抓取→实体→事件→分组→精选→日报全流程。完整流水线须由原版runtime在另一次明确activation和模型预算授权后执行，不能用微任务结果冒充原引擎端到端验收。已有结果模板绑定corpus与annotations精确字节，改动任一文件会拒绝验证。

`validate`检查实际原始文件存在性、长度、SHA、路径边界、身份去重、固定split、关系来源引用与split、占位结果的零指标及输入绑定。完整性PASS只证明冻结字节和模板一致，不证明新闻事实、正文提取、语义标注、来源覆盖广度或模型质量。
