# T3组合包集成元数据核对（2026-10-28）

- 宿主：macOS；任务：Web架构/文档/既有CI登记；工作树隔离，未改产品Python/JS、依赖、服务、凭据或部署。
- 比较基线：`1317968ea7e5e7227adbe9451882b381307438c2`。
- 被说明产品候选：`fca98f25484f8ff341ec0827b7ba3b25172d0b12`，含表单required的P2修复；后续元数据提交由主控记录，不提前称最终候选全门通过。
- 未修改主控旧聚合报告、`.superpowers/**`或历史人工图审回执。

## 实际职责与范围

九包纯确定性核在`scenarios/packs/`，由capabilities版本资源固定源码、record/output schema、golden、解释器及完整依赖/import闭包。原八场景与18个gated算法保持。三个owned方法各自生成原件分析台账，仍通过唯一DSH生成叙事与原报告链；台账`research_quality=NOT_RUN`不能自证报告通过。新闻/调研C2实际由Host调用公共atom并冻结receipt/full-result与SourceSet，Native消费而非再次执行。CLS固定wrapper只对原有界最新快照做严格query/limit适配，未注册供应商alias。C6只读preview不建文件/会话；freeze重验当前授权、proof/hash与能力版本，再经原幂等handoff，只有明确not_created才能解除unknown。

静态140映射、构造资源、实际Native夹具、来源覆盖、模型质量、安装CI和部署分别认证。T4/T5仍待实施；本次元数据工作不认证62/78全项可用，不发模型/供应商请求，不更新常驻。

## 新模块完整映射

下表由基线至候选新增的Research Web源码/资源集合与当前architecture-map匹配；命名空间覆盖不冒充每个模块已有运行验收。

| 新增路径 | 文档组 |
|---|---|
| `app/research_web/capabilities/pack-output-contracts-v1.json` | capabilities |
| `app/research_web/capabilities/pack-record-contracts-v1.json` | capabilities |
| `app/research_web/capabilities/pack-runtime-lock.json` | capabilities |
| `app/research_web/capabilities/pack_dependencies.py` | capabilities |
| `app/research_web/capabilities/pack_equivalence.py` | capabilities |
| `app/research_web/capabilities/pack_import_policy.py` | capabilities |
| `app/research_web/capabilities/pack_logging.py` | capabilities |
| `app/research_web/capabilities/pack_native.py` | capabilities |
| `app/research_web/capabilities/pack_relocation.py` | capabilities |
| `app/research_web/capabilities/pack_resources.py` | capabilities |
| `app/research_web/capabilities/pack_result_contracts.py` | capabilities |
| `app/research_web/capabilities/scenario_method_packages.py` | capabilities |
| `app/research_web/scenario_method_dedup.py` | workbench |
| `app/research_web/scenario_method_sources.py` | workbench |
| `app/research_web/scenario_pack_execution.py` | workbench |
| `app/research_web/scenario_pack_inputs.py` | workbench |
| `app/research_web/scenario_pack_reads.py` | workbench |
| `app/research_web/scenario_pack_ui.py` | workbench |
| `app/research_web/scenario_source_selection.py` | workbench |
| `app/research_web/scenario_source_versions.py` | workbench |
| `app/research_web/scenarios/execution-bindings-v1.json` | workbench |
| `app/research_web/scenarios/execution_bindings.py` | workbench |
| `app/research_web/scenarios/method_catalog.py` | workbench |
| `app/research_web/scenarios/native_argument_adapters.py` | workbench |
| `app/research_web/scenarios/pack_catalog.py` | workbench |
| `app/research_web/scenarios/packs/__init__.py` | workbench |
| `app/research_web/scenarios/packs/atoms.py` | workbench |
| `app/research_web/scenarios/packs/bundles.py` | workbench |
| `app/research_web/scenarios/packs/contracts.py` | workbench |
| `app/research_web/scenarios/packs/format_profile.py` | workbench |
| `app/research_web/scenarios/packs/limited.py` | workbench |
| `app/research_web/scenarios/packs/record_contracts.py` | workbench |
| `app/research_web/scenarios/packs/synthetic_vectors.json` | workbench |
| `app/research_web/skills/_shared/source_actions.py` | runtime |
| `app/research_web/ui/pack-ui.mjs` | ui |

六个新增Host模块已明确登记workbench：method_dedup（Host C2预处理）、method_sources（原件冻结/完成复算）、pack_execution（固定launcher/产物读回）、pack_reads（历史显式等价读回）、pack_ui（原鉴权后的安全投影）、source_selection（安全metadata/内存预览/幂等freeze）。对应owned/source-selection/UI文档和实际回归测试纳入组映射。

## API与图

登记五个真实声明：私有pack-completion、source-selections的GET列表/POST preview/POST freeze、scenario prepare。CLS仍复用原business-query声明，未凭空增加API。

05能力流图补supervisor→Host私有完成桥→原件/产物独立读回。首次候选出现真实标签重叠，按诊断调整两个label位置；validate与deliver分别保存真实回执。没有新DSH/队列/数据库。旧人工图审保留原hash，更新后的截图由主控实际审阅再认证，不能搬用旧PASS。

## 既有CI与安装合同

Research Web Checks原Python步骤追加29个新增实际回归模块，JS保留原通配符。Bootstrap沿原启动步骤，补pack-ui.mjs HTTP/checkout字节比对；隔离`python -I`断言模块来自sys.prefix内已安装wheel并逐件比对checkout，再由已安装builder实际构造9pack+3owned并核资源sha/manifest/闭包，产`pack-resource-smoke.json`。不增job/runner/依赖/timeout或其他平台dispatch，不调用模型/供应商或建立业务会话；资源构造不称Native执行或报告通过。

已核对requirements/web.in、web.lock、scripts/setup_web.py与setup-web.sh/setup-web.cmd，无需依赖/安装器变更。公开安装、固定DSH、3081/8088健康、Doctor和最终候选macos-14干净安装仍须CI真实证明；本机现成3.12环境不能代替安装证据。

## 验证与剩余门

本人仅执行结构/生成/文档/CI语法及离线资源构造核对，不跑整批pytest、不push、不建PR。命令、stdout/stderr、摘要和hash在`logs/seek-packs-integration-metadata-20261028/`；图可信deliver与visual回执在`outputs/research-web-architecture/05-capability-flow.*`。05新图已由Codex /root实际查看四张截图并批准相同source/artifact hash的新记录，旧人工记录另存本人保全JSON；architecture-check-3为189项changedFiles、零violations。完整changed-set Router、最终评审、CI及Mac干净安装由主控后续执行；Windows/Linux保持各设备NOT_RUN，供应商/真实模型/部署无本轮认证。

## 结构决策

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "组合包与原文选择扩展既有场景抽屉、主题和Send入口，未新增主导航或跨服务UI连接；三种状态及权限仍由原Host返回。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "新增接口仍挂载现FastAPI的datahub/workbench路由，唯一Host/DSH/数据服务节点不变；完成桥的内部流程变化由runtime和capabilities的05视图展示。", "diagrams": []} -->

<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "CLS仅新增固定请求变体，仍经原business-query→DataHub.query→broker/provider→snapshot；完成桥不是新数据源，无新增来源节点或存储。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "共享service和能力UI调用发生变化，但未更改Automation调度器、计划存储或外发链；来源选择和场景准备不启动跟踪。", "diagrams": []} -->

<!-- architecture-review {"group": "files", "structure": "unchanged", "reason": "capture proof与冻结输入/制品位于原账号会话及私有控制区，新增逐件hash/proof检查与孤儿拒绝，不建立独立存储或新发布服务。", "diagrams": []} -->

<!-- architecture-review {"group": "runtime", "structure": "changed", "reason": "固定launcher经唯一DSH supervisor完成后调用Host私有完成桥，Host独立重开原件/制品并复算；05明确补实际完成与验证路径，C2仍由Host执行。", "diagrams": ["05-capability-flow"]} -->

<!-- architecture-review {"group": "capabilities", "structure": "changed", "reason": "九包与三owned方法冻结代码/schema/runtime/import闭包，Native执行后需Host独立结果验证；05增两个组件和实际完成关系，未解锁供应商alias或18 gated方法。", "diagrams": ["05-capability-flow"]} -->

<!-- architecture-review {"group": "workbench", "structure": "changed", "reason": "来源列表与preview/freeze沿原handoff增加Host资格/封印，随后经唯一DSH与完成桥独立读回；05展示新增完成关系，原八合同和显式Send保持。", "diagrams": ["05-capability-flow"]} -->

<!-- architecture-review {"group": "dossiers", "structure": "unchanged", "reason": "显式历史等价读回与selection/capture私有文件保全复用现Dossier retention fence和既有SQLite，未增加档案数据库、扫描器或自动跟踪。", "diagrams": []} -->


<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "仅在既有Checks测试参数与Mac Bootstrap原步骤追加静态/安装资源核验，job、runner、超时、依赖及交付平台路由不变；08既有验收拓扑仍准确。", "diagrams": []} -->

## 本人实际执行结果

| 核对 | 实际结果与证据 |
|---|---|
| API Atlas生成与`--check` | PASS，`api-atlas-build.json` / `api-atlas-check.json`；414项源码声明 |
| 架构完整changed-set检查 | PASS，`architecture-check-3.json`，189项changedFiles、零violations |
| Archify validate/deliver | PASS，showcase 9/9、零错误警告；spec `27390c2404bee19424794e4cb8c52b3f6cbabd31d41f29967aac4a5658668b22` |
| 同HTML四视口/四深浅截图 | PASS，artifact `9e4465d58bc29acb8f7f9cec6aedaa7458506ab835e1bf2cad45dabaade0f21c`；Codex /root独立实际view_image审阅并明确批准 |
| CI YAML/shell/Python AST | PASS，`ci-static-validation.json`；原JS步骤完整不变，job/runner/timeout/step数不变 |
| 新增回归登记 | 29个实际新增Python模块均已登记，`registered-tests.json`；整批pytest由主控执行，本人未运行 |
| 本地9包+3方法资源构造/hash/闭包 | PASS，`local-resource-construction.json`；仅读源码，未运行方法、供应商或模型 |
| 真实wheel构建/资源完整性 | PASS，`wheel-build.log` / `wheel-resource-bytes.json`；38份固定文件与checkout逐字节一致，wheel SHA `f67d39b76755292031b9db2ce67767d273993c8728806be331969c34e92009ad` |
| CI实际安装wheel的`python -I`核对 | NOT_RUN，本机未装新wheel，等待最终候选macos-14安装CI，不能由本地构建替代 |

以上相对证据路径均位于`logs/seek-packs-integration-metadata-20261028/`，图回执在上述outputs目录。初次图render标签重叠及首次visual纵向溢出保留真实失败文件；随后根据诊断移动两个标签，合并重复说明卡并压缩原行间距，未用裁切、隐藏溢出或缩字伪造通过。修改后重新validate/deliver/visual均通过，新hash已独立人工审阅。

最初按文本规则尝试`git_safety.mjs delivery ... check`实际CLI_OPTION_INVALID，诊断原样在`git-safety-check.log`；主控确认既有CONTROL已check/start且Harness已建，本人不接管其owner或再次start/prepare。CI静态核对最初用了错误的预期JS通配符字符串，断言失败后改为将当前整个JS步骤与基线按实际YAML结构精确比较；原workflow JS步骤始终未改。

架构专项Node回归实际84/84通过、零skip/fail，命令为固定Node24运行`node --test tests/javascript/research_web_architecture.test.mjs`，完整stdout在`architecture-node-tests.log`，没有执行整批产品pytest。
