# T3-C6a 原文选择后端候选

平台：macOS Mac mini；类型：Web 功能开发；状态：LOCAL_CANDIDATE / REVIEW_PENDING。
产品基线 `6000caa28b4d8d2ab5bea0ad508ade453e63e971`，中间主控纯文档提交 `7a6299ba`。
本切片不发布、不调用模型/供应商/公共网络、不部署、不安装依赖，不代表全 Task2 或 C6 UI 完成。

## 变更

- 新 `scenario_source_selection.py` 与 closed 请求模型提供安全原文元数据列表、纯只读 preview、
  显式 freeze；`research-pack-source-selection/v1` 只列固定 subject/as_of/refs/hash/请求摘要。
- 完整请求、SourceMeta、当前资格及能力版本绑定确定性 preview SHA；真实 manifest 必须逐字节
  匹配账号私有登记，每次新准备均重鉴权/原件/proof/hash/方法资格。重算只在新 prepare/交接，
  旧档案 trusted_context 仍只复验冻结 references，不重做最新 preview 或覆盖 context。
- 仅两个 source pack 派发新文件 reader；沿原 workspace_material/file token、原 create_handoff、
  durable intent.lineage、复制/封印/Native/草稿/Send，未扩 Handoff 原 schema、原八合同或原18门。
- selection-id 绑定完整请求 SHA 与 preview SHA；同 key 变化 409，同请求重复只一份文件/草稿；
  文件发布或 Native 创建未知保持原请求，不重建。manifest 本身不是保全 holder，原 intent 前
  源被清理/撤权即拒绝；原 intent 后沿既有删除 fence 保护所有 source/manifest 祖先。
- 主控明确批准的唯一追加共享点：`dossier_preservation.py` 将新固定私有 receipt namespace
  SHA 并入原 snapshot_dossiers/retention fence，现 multiuser 与 resident @dossiers 自动复用，
  不改 operator、不初始化 Dossier DB。未知受理 key 与 intent 同样纳入。
- `pack_catalog.ui_methods` 使用真实 method_version：去重 1.1.0，其余按既有版本；生成 py index。

## 实际验证

解释器：`/Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python`。
使用主控提供已缓存 PYTHONPATH、PYTHONDONTWRITEBYTECODE=1，未安装包。

| 实际命令/范围 | 结果 |
| --- | --- |
| pytest --confcutdir=tests/research_web test_scenario_source_selection.py test_scenario_handoffs.py test_asset_research_workspace.py -x -q --show-capture=no | 47 passed，249.16s |
| 新保全 consumer RED→GREEN | RED 确证两份私有登记遗漏；GREEN 1 passed，10.83s |
| 最终精确 owned opaque temp：source-selection 的 changed_key / private_selection_receipts / actual_native_guard | 3 passed，14 deselected，44.90s |
| Ruff check / Black --check / isort --check-only：本任务六个 Python 文件 | PASS |
| generate_py_file_index.py --check；git diff --check | PASS |
| mypy | NOT_RUN，既有环境缺 librt；未安装 |

首轮 RED 确证 ui_methods 去重版本错误。初期两次夹具错误分别为裸中文行业身份（现合同正确拒绝）
和直接 purge 未先软删/Native确认（原门正确拒绝），仅修测试输入/模拟 tombstone，不改生产门。

覆盖 stock、规范 industry、中文 topic 保真；preview 零文件/Store/Native/send 写入；安全列表、
重复/外来 refs、同 URL/hash 不同 SID；scope/正文/proof metadata/参数变化；实际 manifest/
lineage/target seal/draft；正确重算上传 manifest SHA 仍因无匹配 Host 登记被拒；同 key冲突；
发布未知只尝试一次；Native outcome unknown 不重复；原 intent 前真实 Store purge 竞争及
intent 后祖先保全。原场景/资产 bundle 回归通过。合法旧 source 的语义继续由现 C2 reader处理，
不升级 proofless capture 的 completeness/角色/语言/地域/PIT。

真实 Native 测试使用固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73`、Node 24.19.0、
原 ToolRuntime/FileSystemSkill/guard、真实 macOS sandbox、Host 私有准入与产物读回。
freeze 时 send计数0；其后仅显式 offline NativeFixture admission，真实 LLM/供应商调用为0。
实际产物 saved，计算 partial、研究质量 NOT_RUN，未将文件保存改为正式报告通过。

## 证据与资源

- 主回归 `/tmp/c6a-final-regression.log`：1,207,333 bytes，
  SHA256 `bebcd13b7b1297d07969b9f2198671688246318a10ce5a6eaaad3d679efbe5e4`。
- 保全 RED `/tmp/c6a-preservation-red.log`；GREEN `/tmp/c6a-preservation-green.log`，
  GREEN SHA256 `55a246fb5a2138eb5a92c4d9f8cc0c5701851fe6bd3a78266c45e4b0ea78e375`。
- 最终 registered temp 的日志、source 原件/proof、manifest/private receipt、冻结输入、Native
  transcript/实际产物共31文件归档，逐文件恢复读回通过：
  `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-c6a-613klqqa-evidence.tar.gz`，
  196,704 bytes，SHA256 `d6f98114a3927ff38775e756b607f8624af02e87e3104cd933753c0ccc7f69b5`。
  同目录 `rwb-c6a-613klqqa-evidence.tar.json` 记录 UID/PID/dev/inode、每文件SHA与回收状态。
- 此明确登记的 temp 已回收。首次回收遇本测试生成的 immutable capability 只读目录而中止；
  核原进程退出、根 inode/UID 不变且证据归档已校验后，仅恢复自有目录 owner 写权限并完成。
  初期测试沿既有共享 pytest 默认根，未逐根建立本任务归属，不据名称/时间推断或删除；这些
  根保持保护、资源总收尾 ROOT_PENDING。未触碰既有受保护50根、其他任务、Docker或常驻。

## 主控待办与边界

ROOT_PENDING：独立 SPEC→Python QUALITY；完整 changed-set Router/Harness receipt、API Atlas、
架构图/七文档/CI 聚合；远端发布与整轮资源收尾。C6b UI/浏览器、其它方法/参数、T4/T5、
真实模型/供应商、研究质量及部署继续未完成；本候选不授予这些动作权限。
