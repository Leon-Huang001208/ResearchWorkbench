# C1/C2：140静态执行合同与本人原文版本后端切片

base `8dad1f15357b1a2c6970448415ff6bf52fc858ad`；任务seek-packs-20261027-7bda5752。
macOS Mac mini Web功能开发；当前本平台Native物理执行，portable资格测试独立保留。
本地提交交root独立SPEC→Python/TS QUALITY。没有push、PR、模型、来源网络、付费、秘密、
依赖安装、常驻服务、业务数据库、部署或其它平台执行。

## 实际变化与边界

C1保留exact140 IDs（62Skill/78Tool）及284原Tool参数/定义hash。baseline原字节不动。
新JSON与只读parser使用固定主路由/固定builder+capability/版本policy和闭合字段、字节SHA；
未知ID、未知字段、伪ready、猜supported、动态module/URL/路径均拒绝。原required未知就写
unknown；原同名alias/参数没有实现，因此显式参数（即使None）稳定拒绝，空参数仍alias
unregistered。十八行仅标已有自有九包动作，原源与Native action/ready/callable/fixture/
live_source/runtime/quality分开。这张无会话的静态合同不执行、不授予权限，不从本轮fixture
或源码把全局callable/quality置绿；动态执行真值属于实际当前Host会话回执。

C2只对经resolve_reference当前owner/祖先/权限/hash重读的source类型投影source-version v2。
新mapper核当前Host web记录结构、实际UTF8/body大小/hash/取得instant；当前reader在落盘前
拒绝超限/失败读取，完整保存capture后只对模型预览截断。full_text_available只表示该冻结
capture正文可读，固定upstream_completeness_unverified。旧/额外声明/真实截断完整性无法
证明则false+gap；模型preview truncated=true没有被误当落盘截断。
语言/地域/原创角色为unknown；自然日发表证据保留原source定位与缺口，published_at/event_at
均None，不造父版本/转载滞后、历史PIT或国内/海外覆盖；coverage始终unverified。
其它source类型、file改名、dataset仍只按原Baostock mapper，不开放任意上传字段映射。

原workbench._copy_evidence只把source原文复制到target page-evidence文件，不登记新的
web_evidence，也不改reference原sid。因此resolve后的原sid/webID是当前规范登记身份，
同原件重复refs逐次复验expected后去重并留转换；不同原始read_source会话登记的同URL同hash
保留不同version/locator(sid+web ID)/observed_at。原子只按bytes分组，不推断独立上游。
原件更新/更改取得时点/任一来源或target撤权不能替换旧sealed输入或继续结果再读。

使用现有workspace_material→asset-research bundle→原source引用进prepare/封印，显式
scope仍datahub/uploads/web，不扩旧八合同、API或UI。两个包经真实Host→DSH ToolRuntime、
FileSystemSkillProvider/guard→research_run_script→macOS sandbox→产物/Host独立读回运行。
fixture为既有冻结统计局真实正文；当前fetch是离线替身，实际read_source落盘/哈希/封印
及Native计算是真的；本轮live取数/真实模型仍NOT_RUN，文件保存不代表正式研究通过。
原atom/record schema/九包数学与输出协议、18旧比较门没有新增改动。

C6仍须真实source选择器/结果可见UI；当前dataset picker不等于本切片UI闭环。现有workspace
材料流可接source；pack_catalog.ui_methods版本投影仍固定1.0.0，C6需沿真实method_version
展示去重1.1.0。C3真实可选公司/新闻/调研方法、C4 typedDataHub、C5真实MCP、T4/T5继续后续。
本切片不宣称T3或全部62/78完成。

## TDD与实际验证

- 初次source fixture缺completed搜索状态，被现source身份门拒绝，日志保留于C0日志目录
  `c1c2-red.log`；不是功能RED。随后正确fixture的source-red：两包真实原件存在仍blocked，
  2 failed/8.25s，证明待补mapper。
- source-green：14 passed/32.08s，含两包资格、权限/hash/foreign/未知取得/legacy/truncated
  与原284参数逐项拒绝。
- duplicate-red：真实同原件重复引用触发duplicate_row_id/aggregate invalid，1 failed；
  修复只在resolve/expected之后去重，不跳权限再读。
- source-neighbor单轮：36 passed、2 deselected、1 failed/129.96s；唯一失败是失败用例在
  Sandbox前置hash校验即正确拒绝而非返回进程结果。改为保留完整输入、真实writer拒绝
  prewritten output_exists，实际sandbox进程failed、Host状态failed且不准重试。
- source-negative-fix：19 passed/39.62s，含真实失败writer、duplicate/different capture、
  取得晚于历史截止拒绝、两包完整capture语义和严格binding变异反例。未把前轮失败覆写。
- 格式后final-native：15 passed/41.91s（2包真实DSH成功与13绑定测试），源码SHA逐文件
  在receipt，source_unchanged_after_run=true；日志SHA
  `2c26074ba996b84b26896867c42f2b702e88fffedb38a60c77d9392e0213348d`。
  两成功例已绑定最终sid locator/去重/helper；仅这两例有依据复验，没有重跑138全套。
- 真实Native取消沿既有driver实际执行且恢复后不准retry；成功保存后撤原scope结果GET403。
  多bundle去重、同hash不同登记、旧封印/源/target撤权、原文/取得时点变更、真实不同
  account Store、缺材料/历史取得/PIT拒绝均有portable资格/Host反例。
- 真实sandbox/Native成功、取消、失败各单独Darwin marker；portable用例没有整体skip。
- Ruff、Black五文件、isort、pyindex生成并check、diff check通过；首次ruff指出unused
  fixture变量的预检保留，显式修复后通过。Mypy本slice未执行（现环境缺librt的已知状态）。
- 测试helper仅从私有真实descriptor取固定已知九包Skill ID，保留原event-review值；Node
  --check通过，3个非canonical ID在任何DSH导入前拒绝。生产JS/注册未改。
- 实际wheel构建并逐字核6份当前source/绑定JSON/旧v1合同入包；wheel-resources.json。
  这只证明资源入包，没有宣称安装、CI、部署或正式报告passed。

## 完整性未关闭项交接

本slice **架构完整性NOT_PASSED / ROOT_PENDING**，原失败日志architecture-check.log保留。
root明确统一做最终完整changed-set：

1. `docs/architecture/research-web/architecture-map.json:/groups/11/sources`仍缺既有B1
   scenario_pack_execution.py、scenario_pack_reads.py、scenario_pack_ui.py；本slice只新增
   owned mapper及已改inputs分组，未扩写旧B1清单。
2. `/apis/-`须据真实源码补POST `/api/research/internal/data/pack-completion`
   （datahub/routes.py）与POST `/api/research/scenarios/{scenario_id}/prepare`（workbench.py）。
   它们已经实际注册，清单补记不应改变公开行为。
3. `/groups/11/documents`要求全部7份模块文档、报告architecture-review marker统一更新；
   本slice只更新自己的research-packs/ARCHITECTURE/DEVELOPMENT_MAP与本报告，不机械改全7份。
4. 机器清单变化后 `node scripts/build_research_web_api_atlas.mjs` 生成index/api-atlas，
   再由root执行完整 `node scripts/check_research_architecture.mjs --project <WT> --base <base>`。
   当前index.html stale，不把选择性文档更新说成完整性通过。

原baseline SHA92a0c404...与八合同d97fccf1...保持。最终全Router、本平台Mac干净安装/固定DSH/
健康/Doctor、CI、独立双阶段评审由root绑定最终候选；其它平台和live/quality不冒领。

<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"C1/C2 stays inside the existing Host evidence qualification and frozen Native execution edges; no engine, service, storage or public API node is added; complete inventory and generated atlas reconciliation is pending the root final changed-set.","diagrams":[]} -->

## 本轮资源收尾

10个本轮明确登记的opaque临时根（含初次使用C0命名前缀的C2搜索fixture预检根）完成
UID/PID/owner、无open复查、43份必要产物/Native transcript/owner归档并hash读回后回收，
回收1,563,555,337字节；`logs/research-packs-c1c2-20261027/c1c2-owned-closeout.json`记录
每个原路径、dev/inode、归档SHA与读回文件digest。只对本人临时测试目录恢复owner写权限
后清理，未操作旧50、reviewer根、Docker、常驻服务或其它worktree。早期C1三文件备份
`/tmp/parity-c1-pending-7bda5752`继续保留给root，不混入本轮cleaned根。
这是本slice临时资源收尾，不表示全任务project closeout已cleaned。
