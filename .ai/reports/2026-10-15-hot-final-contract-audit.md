# Hot 完整合同复核与恢复边界修复

宿主macOS，功能开发；本机Native、Mac Docker Desktop及macOS CI验收范围不变。
本复核覆盖PR114的周期报告、恢复精度及Docker纯投影修复；旧PR113保留失败运行及修复历史，
不作为最终交付。实际运行证据绑定3182d0a2；后续仅本文档修订的候选仍须绑定最终评审及CI。
全Goal仍ACTIVE，以下是分项审计，不是完成声明。

## 逐项合同与现有证据

| Goal章节 | 实现与证据 | 当前边界 |
| --- | --- | --- |
| 1–3 产品、复用及基线 | 研究情报统一入口，保留8外部栏目；services/hot/THIRD_PARTY_NOTICES.md记录后端8e34e05与前端652bd6b、MIT/NOTICE和修改范围；PR114基于master4eb4d31b并保留旧候选祖先 | 不把旧PR106/113当作最终已交付能力 |
| 4 责任与边界 | 唯一TS/PG引擎、pg-boss、controller/reader/worker角色、签名回环、代次租约、惰性Host；service/control/queue/provision与真实PG/RPC测试 | 不启动第二ResearchService，不并发写旧Store |
| 5 数据库与配置 | 受管PG17.11固定镜像及独立卷；外部verify-full实际TLS1.3、错证书/CA/明文拒绝；配置/CLI/Settings/Doctor/停机保卷 | 外部用户指定远程库未给定，不声称已连通；本机外部pg_dump17工具链未单独验收 |
| 6 不可变资料与时间 | raw bytea、发现/材料/版本、日期原件引用、修正审计、PIT、会话冻结副本；event-dates、research-evidence与联合恢复 | 不用取得时间伪造发表/发生/生效；Native执行历史不在联合恢复范围 |
| 7 真实采集 | OpenAI/DeepMind两独立AI主体、Fed/ECB两独立宏观主体；The File新增非官方来源默认禁用；真实多轮/重启/来源设置和覆盖回执 | 当前RSS没有next时仅latest_snapshot；历史两文章明确操作员partial导入，不冒充自动完整历史 |
| 8 事件与纠错 | 独立热度/重要性/增量/证据；跨频道同ID；merge/split/reassign/标题/频道/日期修正；19次模型误判保留并审计纠正，20次真实same_occurrence/direct_followup/composite与2022→2026链 | 品牌guard不是全面事实校验；无开放新闻零误判承诺 |
| 9 任务、回执与预算 | 领取租约/条件提交/迟到拒绝/原文先存/回执先存/未知管理/缓存复用；真实预算拒绝探针 | 同scope最终20calls、79894tokens、11501microUSD保守费率上界，非发票；上限20/100000/USD1，不再付费 |
| 10 页面、关注及简报 | 频道/筛选排序/覆盖/纠错/关注/计划/冻结简报；schema21周期运行自动调用既有报告机制的一次性子执行，MD/DOCX及回执先存PG，再提交completed；Native及Docker真实Word和重复下载同hash | Gold验证间接银行稳定性规则，非黄金价格来源；旧周期没有报告回执时不追认自动报告；不新增DSH请求 |
| 10 研究交接 | 固定run/session/deliveryKey；accepted结果丢失先查原marker；test_hot_session_recovery/test_hot_execution；2734bytes真实报告e98d29ac…及Word导出 | research run最终failed、delivery completed分别如实展示；不为得到completed再发模型 |
| 11–12 恢复、切换及平台 | 3182候选59表、全部周期报告原件及选定真实研究报告联合恢复；恢复worker schema21且4源取得本轮新成功；Docker136→Native138→139暂停，旧owner拒绝，stage停止、dev/g2b原身份恢复 | DeepMind保留旧成功及连接重置错误；Mac CI须以最终候选终态认证；Windows/Linux产品真机/同平台CI保留NOT_RUN交接 |
| 12 真实评价 | v1五材料/三回执：2开发/3回顾留出，context有交叉；新两次真实关系运行另存不重写v1 | 不是独立盲测/人工金标准/准确率；v1四条NOT_RUN参考保持历史真值 |
| 13 交付 | PR114、权威continuation进度、exact SHA/tree/CI checkout及实际运行证据保留 | 未合并/部署；必需测试、最终CI及评审绑定完成后按持续授权合并 |

独立需求审查指出周期冻结后completed但无自动报告子执行的缺口，现已按用户明确要求
补schema21：Hot唯一调度领取固定run，私有产品Python调用既有brief_docx/report_documents，
原件及回执先存不可变PG，完成与claim/pg-boss同一controller事务提交。恢复重用已有回执，
reader仅取已存字节。旧周期无回执不追认新能力，不新增DSH请求或第二调度事实源。

实际正常Native worker已完成真实宏观周期子执行：run e6500e8d-d9db-54b3-9eb0-3b3cf9887b06，
execution 286591dad8ac287b7bedd58cb8536602b2ebfb1b371db69b72f99cc4bdf1e972，Word38932bytes，
SHA cdaea2362d307b71cef97b9b1b6a7019c96665c09637eee3ea066a49c0e47d95，41行文本、完整周期及
来源依据；两次真实Host HTTP200下载同字节，未调用模型。计划最后version3停用，正常
Native132后停止（库133暂停）；原授权预算保持20/79894/11501microUSD。证据logs/periodic-final/。

## 三项P2及修复

1. 选定研究归档：metadata加入后统一检查64MiB展开总量，关闭ZIP后检查实际ZIP同上限，
   只有两者都满足才写签名manifest。失败残件保留，不声称成功归档。测试覆盖payload和ZIP边界。
2. 报告核验：去除累计16MiB/5文件的截断，沿既有Delivery合同核验100文件/每文件16MiB，
   64KiB流式SHA；超限明确抛StoreError，不将扫描不全推进PG failed。测试覆盖MD12MiB+
   DOCX8MiB，以及第六文件满足required格式。测试字节是已验证交付回执的夹具，非真实Word生成验收。
3. PG精确恢复：原to_jsonb→JS Number→JSON.stringify可能产生大整数碰撞。
   新归档直接哈希to_jsonb(t)::text，签名包含inventoryEncoding=postgres-jsonb-text-v1。
   旧hash无法逆推出原始数字，连“当前恢复值可roundtrip”也不能证明旧值无损；因此未标记编码
   明确拒绝自动恢复认证，要求从保留原库重新backup。旧档/镜像/卷不删除、不直接改签名。
   真实PG反例覆盖bigint和嵌套JSONB相差1、两方向legacy碰撞及验签旧manifest拒绝。

## 验证与后续动作

当前证据目录为feature的logs/final-review/。真实PG archive.integration.ts与TypeScript
typecheck已执行通过，包含实际pg_dump/pg_restore、原文bytea相同、暂停状态、New_York会话
时区下UTC规范inventory和精度篡改拒绝；
早期端口配置沿旧receipt导致ECONNREFUSED，改为测试专属显式58154端口后实跑通过，失败日志
不得被解释为曾成功。Python边界测试首轮ZIP夹具计算不准确（20 PASS/1 FAIL），修正夹具后
再次执行。最终Hot Python72 PASS、Hot单元67 PASS、UI39 PASS、类型/编译/文档/架构/约束
通过，Git安全check实际fsck PASS。原Delivery首轮23 PASS/8沙箱超时，最小真实import/save
诊断与单项复验通过后，8项以原15秒与原权限完整复验PASS；不改变sandbox，不声称已确定
瞬态超时根因。容量竞态用例改为有界等待真实线程完成，不放宽产品deadline。
独立Python/TS审查关闭三P2及新子执行边界，最后Docker解释器/UTC/链接修正复核批准。

最新3182候选59表联合恢复包括全部周期报告原件/执行回执与选定2734bytes真实研究快照，
原文/事件链/修正/完整20次账本均保留。隔离恢复DB hot_joint_final_3182_20261015正常worker
启动schema21，ECB/Fed/OpenAI/The File四源取得本轮新成功，DeepMind保留旧成功及连接重置
错误；五源配置/旧材料版本保留，预算不变，clone141暂停。原Native Word38932bytes与新
Docker Word38933bytes均逐字节和SHA验证，Native执行历史明确NOT_RESTORED。
当前integration的logs/recovery-final/{joint-final-receipt,joint-final-pg-receipt,runtime-receipt}.json
为对应证据。旧hot_joint_periodic_20261015及其归档不删除，旧轮仅Fed/OpenAI新成功仍为历史事实。
恢复driver最后打印摘要曾取错status.database键而非status.schemaVersion，实际子进程及
已保存完整runtime-receipt终态PASS，摘要错误保留，未重开相同已完成任务。
首次Native证明漏设源PYTHONPATH而误载已有安装包，启动前runtime_contract_changed拒绝；
修正验收driver按源运行后正常产品链通过，无安装新包或改动已安装的全局包。

Docker镜像afd1dc1938e383255bb70a57587c3fd00da1aae6b89d47d8a7a4cdc63610ccfd绑定3182d0a2，
真实自动周期run 8ead2654-6ce4-57ab-a74c-a505853682dc生成38933bytes Word，SHA
196c779734b049b3277396b980f3be7fbadede662f93e916fdc4f46f42eab171；跨模式读取旧Native Word
不变。Docker仍如实blocked_model，公开采集及报告投影正常。验收连接使用本机专属TCP relay，
不冒充用户外部TLS环境。stage已停止，dev/g2b同CID、旧镜像及全部五卷保留。
仍需：最终文档候选的完整检查回执、Mac CI与评审绑定，然后按持续交付授权合并；不以
本局部审计代替这些门。最新UTC联合恢复已终态通过，不重复执行或覆盖旧目标及归档。
本切片无新增依赖、付费模型、外部消息、卷删除、常驻生产服务更新或预算增加。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"修复既有PG归档校验和报告边界，保留唯一引擎/队列/签名控制，不新增服务或schema；新manifest字段版本化精度编码并明确旧档重备份。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"既有选定快照归档在相同路径补payload与ZIP限制，恢复目标及运行归属不变。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"原周期卡片新增固定同源Word下载和不可变回执投影，文本转义及runId编码保持，未新增页面控制器或自动收费交互。","diagrams":[]} -->
