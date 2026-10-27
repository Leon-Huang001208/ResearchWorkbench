# T3-B2 九包前端消费与交互

宿主 macOS Mac mini；任务类型为 Web 功能开发。本报告只覆盖九包 UI／既有 Host 契约消费与只读结果投影，不表示 T1–T5、140 项执行绑定或 62 Skill／78 Tool 的全部功能完成。基线 `d812dc0e1eb21aeecbbc1e8500c13e35f1980042`，任务 `seek-packs-20261027-7bda5752`。只作 scope 本地提交；未 push、prepare、合并或部署。

## 变更

- 原场景抽屉支持九包中文选择、当前本人快照、本人原会话材料选择、类型化研究参数、明确时区、只读 Host 资格预览与逐来源缺口。日期不默认午夜／日终，证券范围不推断市场／币种，禁收 caller 权限、来源事实、coverage 或任意 records。
- Host `pack_catalog.ui_methods` 为现固定 METHODS 的只读表单投影，不改算法、资格、封印、Native、18 旧算法门或公共 baseline/contracts。
- 编辑参数／材料／来源使预览失效；原件或方法变化由准备／发送原门再检。未知创建继续绑定原 key/body，只查询；只有服务端 `not_created` 证明恢复编辑并要求重新预览。旧文本、附件、模式、原八场景及基金路径保持。
- 能力中心保留原复制／编辑／检查／发布路径，新增当前方法配置入口。草稿仍交给原 Send，不自动创建／发送。
- 新只读 `scenario_pack_ui.project` 在现 detail 当前账号／祖先权限门后，重用 B1 全量产物审计与文件索引投影真实文件引用、计数、omitted、hash、计算状态。未知不判成功、篡改不开放成功链接、撤权／外账号不泄结果。无控制路径、命令、环境、binding 或正文投影。
- 结果界面区分完整文件保存、计算 partial／complete、会话状态与正式质量 passed／incomplete／invalid；沿原文件、质量面板与资产档案先预览再归档，不改 thesis／quality。128 只是 preview，full-result 不是原始来源。

视觉沿原密集信息风格、现主题 token 与抽屉层级，无新导航、依赖、组件框架或 CDN。方法／风险缺口不会因卡片或 runtime_verified 自动通过。

## 实际验证

固定 Node：`/Users/leon/.research-workbench/toolchain/node-v24.19.0-darwin-arm64/bin/node`。
固定 Python：`/Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python`，`PYTHONDONTWRITEBYTECODE=1`。
Python 只复用现装五个 uv archive cache，未安装任何包；black/isort/ruff 复用已安装 archive 工具及其已存在闭包。

| 命令／证据 | 实际结果 |
| --- | --- |
| `node --test tests/javascript/research_web*.test.mjs` | **1238 passed / 0 failed / 0 skipped**，10.076 秒；`logs/pack-ui-full-js.log`。`RWB_TEST_PYTHON` 为上述解释器；`DSH_SOURCE_ROOT` 与 `RWB_DSH_TEST_SOURCE` 均为已安装 pin `/Users/leon/.research-workbench/runtime/dsh/7ecf564f2e09b829240c5553687223bdd1e2df73`，离线 source tests 全执行，不将 loader 登记当真实模型执行。 |
| `python -m pytest --confcutdir=tests/research_web tests/research_web/test_pack_ui_projection.py -q` | **3 passed**，50.13 秒，1 个既有 Starlette 弃用警告；`logs/pack-ui-python.log`。真实 Host + Native macOS sandbox 保存／下载三个产物；unknown／篡改／撤权／外账号与 caller 权威反例保持拒绝。 |
| `node tests/e2e/research_web_packs_real_backend.mjs` | **20 checks PASS**。真实临时 Host，九包在1440／390宽度逐项预览、本人原会话材料选择／明确勾选、6000字输入／预览失效、Light／Dark截图；事件包明确准备→原 Send。无 pageerror；真实模型 NOT_RUN，Native prompt 为离线夹具。最终结果见归档 `browser/result.json`。 |
| 原 `research_web_scenarios_real_backend.mjs` 全部断言 | **4 journeys PASS**。仅把执行副本的 output/log 改到本任务目录，原脚本未修改，覆盖旧八场景入口、原草稿保留、Enter／Tab／Escape、观察切换竞争、材料比较拒绝后纠正与原基金交接；`logs/pack-ui-old-scenarios.log`。 |
| `ruff check`、`black --check`、`isort --check-only` | 本次5个 Python 改动文件通过；见对应 `logs/pack-ui-{ruff,black,isort}.log`。 |
| `/usr/bin/git -c gc.auto=0 -c maintenance.auto=false diff --check` | 通过。 |

新 UI 用例先观察缺少 preview／typed form 的3项失败，再实现修复；共享全量曾发现4个旧 DOM closest 夹具过宽冲突，已收窄真实 dataset 判断；B1 新增9包导致原 fixture 的30计数过期，改为真实 `len(SKILL_SPECS)+len(PACK_NAMES)=39`，保留每项名称／选择／禁用断言。真实浏览器曾拒绝跨证券基金材料，后明确只勾选 BaoStock 原件；未放松身份门。Python 负例按实际400／409／403拒绝语义断言，未放宽任何生产门。

## 状态矩阵与边界

已验证：loading／无材料／blocked／partial／error／stale、预览迟到、原会话切换迟到、账号变更门、显式时区、禁 caller 权威、未知创建原 key、not_created 后重验、Enter／IME／键盘抽屉、长代码与窄屏换行、明暗主题、真实来源撤权／产物变更／外账号拒绝、真实保存／计算 partial／质量 incomplete 分离。

当前仅 BaoStock 不复权日线具有映射；八个缺必需输入的包 blocked，事件包也只是有限 partial。事件收益、基金穿透、财报监控仍 blocked，不宣称九包研究完成。用户结构化声明未在 UI 新开输入通道，不升格为来源或 passed。

NOT_RUN：真实模型、真实供应商／付费调用、生产个人登录、常驻部署、最终候选 Mac 干净安装 CI、Windows／Linux。完整 Router、SPEC→TSQUALITY 独评、B1 后端邻近回归与远端交付由主任务负责；本次本地通过不替代这些门。

## 资源与证据

浏览器独立 context、合成验收账号、合成快照与网络拒绝边界；页面恒显“隔离验收样本”横幅。子进程 PID／UID 在 `owner.json` 记录，浏览器关闭并等待本任务 Host 子进程退出，原临时资料根由原 fixture 清理。不触碰个人浏览器、常驻服务、凭据或其他测试根。

归档：`/Users/leon/.codex/artifacts/seek-packs-20261027-7bda5752/ui-631bc54bbf8c`。30份文件，共1,947,255字节，逐文件 SHA-256／大小与复制前原件一致并读回 manifest 后才移除本任务 `outputs/research-web-packs-ui` 及已归档的本任务日志副本。未删除其他 outputs／日志／测试根。早期失败回执保留用于审计；最终 `browser/result.json` 明确 PASS，旧4旅程证据完整保留。所有截图仅为合成验收材料。

| 归档相对路径 | SHA-256 |
| --- | --- |
| `manifest.json` | `1ab6433672ba148e6b1e02023b944dd7dc63879781f628a5bdb49c45f1b19224` |
| `logs/pack-ui-full-js.log` | `30d4db0fc7dfb9fd9630c03166b234a322a264646a4935151811db6c8a10bd8a` |
| `logs/pack-ui-python.log` | `af7e966a6d90f56917b7693fd59584ea5400a3e5236875316a44187a3195c0c6` |
| `logs/pack-ui-browser.log` | `bd93bb4d8a2487b708f842488f7d1e72d8d471c1403a0215df9a156b961c0e06` |
| `logs/pack-ui-old-scenarios.log` | `d7d3ecb7d7f87af0db734b121a67b2fb0ec0f1db481c2149863f50a702f083b9` |
| `browser/result.json` | `2f3713584d6cb0757c080ca0a5a2fd8c15a083648742bc12556d5fc3fb4d4df7` |
| `browser/partial-dark-390.png` | `ec5eda1fbc0e86b026a8599e7cac6a19dba9f7a61d3fcb7df6b957dce2a5b84a` |
| `browser/draft-1440.png` | `6e243c03ec91fa59029a225ab9261d6ee21e75e467081f8863df005e90360a6f` |

已目视核对390暗色缺口和1440原草稿截图，布局／主题均沿原界面，partial与尚未验收保持可见。完整命令日志和其余截图逐项 hash 见 manifest；路径只用于任务证据，不写入产品配置。
