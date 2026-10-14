# Hot 真实样本与回顾复核

macOS功能开发，父候选813d17af8。原PG generation99暂停；离线前后scope hot_events_goal_01a11684仍18calls/77375tokens/10464microUSD，上限20/100000/USD1，新增模型调用0，无新依赖。

冻结五个真实原PG材料版本，AI OpenAI/Google与宏观Fed/ECB共四独立运营主体；两个目标发生为development，三个为retrospective holdout。保留原件页/材料版本hash、完整冻结row hash、已付费packet/response及其hash和规则版本。范围为feed标题/摘要，空摘要保留。三份真实模型回执均为different_event，不新发请求或写PG；规则逐例验证相关/无关、低热度重要官方信息和空标题上下文限制。ECB会议标题本身不足以判定政策事项，规则零分不表示现实重要性低。

数据和方法不独立于开发者。回顾划分、非blind、无独立金标准，independentAccuracy=null；不输出准确率。真实held EmbeddingGemma packet包含development AI Jam候选：只认证主目标事件/材料分离，输出storedReceiptContextDisjoint=false及具体candidateContextOverlap，原回执保持字节/语义不变。

四个来源核对参考覆盖同一发布的转载、BNP 2022→2026多年整改后续、2022通告的多银行事项和上下文不足。前两类来源有官方2022/2026原文及TheFile追溯说明，不仅靠同主题；参考文章不冒充已由产品采集或入PG。模型状态均NOT_RUN，其他关系既有工程回归不能替代真实模型。FDIC原列表403，不用镜像充当已接通来源。

Source corpus: services/hot/evaluation/real-corpus-v1.json，SHA256 bb9c09dd3fd6f02e79068e8671940463160b65ddac8f992c56bd1433187af67e，25282bytes。公开内容/响应，不含秘密/Prompt或SDK配置；packet仅持久公开材料/候选。离线命令node services/hot/scripts/evaluate-corpus.ts，读文件和纯规则，无credentials/PG/runtime/model sender。

RED缺evaluator模块；2项评价反例与全部61项TS单测、类型检查通过。反例覆盖主事件/材料ID/URL/参考URL跨分区、变更原件字段、不同主体、篡改响应及规则漂移。限定审查指出三P2：硬编码official、材料只验证hash格式、忽略跨分区候选上下文；按冻结目录绑定/完整row与packet验证/真实重叠披露修复后关闭。实际replay状态PASS_RETROSPECTIVE_REPLAY_WITH_EXPLICIT_GAPS，4模型未验项保持。治理111、文档/项目约束/索引及Git完整性通过，完整变更集Router未降级。

证据logs/hot-resume/evaluation-replay-reviewed.json、evaluation-budget-receipt.json及evaluation-public-inputs.json。完整Goal继续：困难关系模型覆盖仍待审计，最终最新联合恢复/整镜像与Native-Docker切换/安装/当前MacCI和受管交付尚未认证，不以本离线PASS收缩目标。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"版本化公开样本及显式离线只读复核，复用canonicalGroupingInput/scoreChannel，不新增PG、服务、queue或付费路径。","diagrams":[]} -->
