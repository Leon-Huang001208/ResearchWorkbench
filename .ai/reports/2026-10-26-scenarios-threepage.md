# T2 三页场景交接实施报告

状态：**DONE_WITH_CONCERNS**。本机 macOS Web 功能开发与隔离验收完成；独立评审、完整Router、
远端CI／同候选Mac安装、真实模型／供应商／常驻部署由控制任务分别处理，未冒称通过。
工作树为既有 `seek-parity-20261026-3af31de6`，起点 `0c8ee56a3d44ea8f89242865abaf36193e2062ba`。
未创建第二worktree／Harness，未安装依赖、push、merge、部署、访问生产凭据或调用真实模型。

## 实现

- 八个冻结T1合同进入实际只读目录和可操作场景表单。当前已发布包／版本与当前执行准入分别报告，
  只有真实准入为true才进入T1资格表；缺口仍为incomplete。纯目录、62／78映射和哈希未改。
- 行业一页纸可以另行填写独立分类身份；不从证券代码推断行业关系，转换时清空证券材料选择。
- 资产页标题提供场景入口，原两个 `data-workbench-handoff` 按钮已有实际事件处理。
  证券取当前本人观察，截止日显式选择，不用今天或最后行情日替代。已取得数据可逐项选择。
- 交接全请求哈希绑定，同键改内容409。场景在普通create前持久未知意图；未知不重建。
  浏览器按账号保留原请求，刷新后查同键，404不旋转键；明确发生在create前的输入拒绝可修正。
- 原件使用既有档案解析器重验归属、原始字节和来源授权。上下文仅记录身份／哈希／方法；
  数据复制沿现有DataHub。发送、数据行／下载和文件预览再验原来源，撤权后不能从新复制文件读取。
- 实际send服务器重建场景要求，绑定身份、截止、输入、能力版本、原件和source_scope到幂等payload，
  同时写入原质量合同与实际原生提示。原能力readiness、原生发现、方法和报告门保留。
- 新target session隔离另一对象的档案授权；原问题／附件／档案draft仍保留。服务器也拒绝给
  场景混入 `dossier_handoff_id`。新增场景来源为datahub，不扩大到web/uploads。
- 问答展示冻结方法和证据缺口，自动格式取冻结能力的真实default_formats；原有显式格式选择
  保留。原成果、来源、追问及档案入口沿用，不自动编辑观点。
- 资讯按有界当前返回集筛选来源／关键词／分类／日期／来源重要性／自选；未知日期排除，
  自选必须有真实资产关联；无热度字段不造排行。选择完整材料身份和内容Hash，未声称任意网页全文。
- Discovery新增可选场景v3，保留原七字段请求摘要与v1/v2字节，沿原selection、prepare、review、
  execute及未知不重发机制。新场景限定datahub，旧通用交接不迁移。
- 独立暖灰主题抽屉兼容390px／1440px，按原主题变量渲染，支持焦点保留、Tab边界、Escape、
  背景inert、加载／空／失败／不可用／未知状态。新增用户状态使用中文。

## 实际验证

所有命令在本工作树运行，完整stdout/stderr位于 `logs/`。

| 验证 | 结果 | 日志 |
| --- | --- | --- |
| 初始Python反例 | 目录不存在、同键改context仍返回旧结果：2 FAILED／8 PASS | `t2-scenarios-red.log` |
| 初始Node日期过滤反例 | 未知发布日期错误进入已知日期范围：已复现 | `t2-scenarios-node-red.log` |
| 真实Chrome首次旅程 | 复现pushState未执行showRoute，已修复并重验 | `t2-browser-backend.log`、最终截图 |
| Python完整聚焦回归 | **120 PASS**，1项既有Starlette弃用warning | `t2-backend-final.log` |
| Node场景／原资产图表／区间／导航／档案／资讯／composer回归 | **365 PASS** | `t2-node-final.log` |
| 真实临时Host + Chrome两视口 | **PASS**，实际表单、HTTP、冻结、进入QA、旧草稿保留、准备零模型 | `t2-browser-run.log` |
| 实际send与Discovery execute | 包含于Python；真实Host质量合同、幂等receipt、原生提示验证；NativeFixture替身 | `t2-send.log`、最终回归 |
| Ruff／Black／isort | PASS，未新增依赖 | `t2-ruff.log`、`t2-black-check.log`、`t2-isort.log` |
| JS语法与diff空白 | PASS | `t2-js-syntax.log`及git diff --check |
| MyPy | **未通过：13错误／5个导入文件**，不在本任务修改文件中；基线归因待控制任务对比 | `t2-mypy.log` |

Python命令：

```bash
PYTHONPATH=/Users/leon/.cache/uv/archive-v0/v7TGbdM8q5alf7K0:/Users/leon/.cache/uv/archive-v0/kcc-PJGC25EjHvMq:/Users/leon/.cache/uv/archive-v0/oI-0I7odtjpBJjwl:/Users/leon/.cache/uv/archive-v0/zdffqOb6hg1LqITK:/Users/leon/.cache/uv/archive-v0/7z-45qlp5-uTFIgN /Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python -m pytest --confcutdir=tests/research_web tests/research_web/test_scenario_handoffs.py tests/research_web/test_workbench_operations.py tests/research_web/test_discovery.py tests/research_web/test_discovery_routes.py tests/research_web/test_discovery_tracking.py -q
node --test tests/javascript/research_web_scenarios.test.mjs tests/javascript/research_web_composer_menu.test.mjs tests/javascript/research_web_discovery.test.mjs tests/javascript/research_web_asset*.test.mjs tests/javascript/research_web_workbench.test.mjs tests/javascript/research_web_dossier*.test.mjs
```

MyPy完整最终命令（没有ignore／follow-imports弱化）：

```bash
PYTHONPATH=/Users/leon/.cache/uv/archive-v0/LFATvV204kt4AbRh:/Users/leon/.cache/uv/archive-v0/6EvMPkhT8ScqCsai:/Users/leon/.cache/uv/archive-v0/vqigiLXjMCLGAtsa:/Users/leon/.cache/uv/archive-v0/NVc3Vbz9TRdVLjyM:/Users/leon/.cache/uv/archive-v0/2fOdTQeHDrbnvgJc /Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python -m mypy app/research_web/scenario_handoffs.py app/research_web/workbench.py app/research_web/discovery
```

首次缺 `ast_serialize` 导致工具内部错误（`t2-mypy-diagnostic.log`）；最终只增加已存在的只读缓存
LFATvV204kt4AbRh。最终错误在 `data_layer/adapters/wind/wind_adapter.py`、
`research_workbench_entrypoint/hot.py`、`hot_model_controls.py`、`hot_manager.py`、`hot_pricing.py`。
“未修改文件”不等于已证明既有错误，控制任务另做基线比对。

浏览器命令使用上述pytest缓存PYTHONPATH，加
`RWB_TEST_PYTHON=/Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python node tests/e2e/research_web_scenarios_real_backend.mjs`。
临时Host生命周期关闭、socket／DNS只允许loopback、凭据全内存、Chrome阻止外部来源；
`outputs/research-web-scenarios/result.json`、四张before/prepared截图保留本地，不提交测试产物。
`scenario-390-before.png` 已实际查看，确认抽屉滚动、底部操作、窄屏布局和对比可读。

## 风险与明确未验

- `chanlun`、`event-review` 等既有禁用或比较证据门没有开启／替换；不能声称八场景全部可运行。
  目录准备、真实执行准入、报告质量是不同层次；实际模型质量、收费／私有来源均NOT_RUN。
- 当前支持整份选材身份，不实现任意字符选段；符合brief的完整材料身份分支。来源缺少
  资产关联、热度、日期、关系、会计口径、历史PIT时保持缺失。
- 普通场景创建丢失回执后只报告未知，没有可证明的target时不自动恢复。旧无请求哈希的
  legacy handoff不猜测重放身份。
- 浏览器实测覆盖QA准备及导航；资产／资讯事件链另由Node与真实HTTP测试证明。
  生产登录页面、真实供应商取数、真DSH模型、生产部署、Windows/Linux均未执行。
- 本任务不修改安装／CI／Router受管文件。控制任务应将 `scenarios.mjs`、`scenarios.css`、
  Python场景路由测试及浏览器脚本纳入既有静态检查和完整交付门。
- 控制任务的 `.ai/reports/2026-10-26-seek-alpha-core-parity.md` 和整体计划保持未提交。
  本报告／独立交接文档为T2所有；未处理其他任务资源。
