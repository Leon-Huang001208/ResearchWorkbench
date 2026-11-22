# ResearchWorkbench 许可范围与第三方声明

[ResearchWorkbench Source Available License 1.0](LICENSE.md) 适用于自包含本文件与许可正文的首个主线提交起，由 Yongjia (Leon) Huang 拥有或有权依新条款授权的 RWB 原创材料。其余材料的许可取决于各自的权利来源。本文件列出的目录与路径整体排除在新许可之外。文件未列入排除项，本身不足以证明其权属。基线 `5a107ced93ec47f1fef0ed3f83830328c9907215` 的 README 声明 MIT，已经有效取得的历史许可继续有效。 [基线 README](https://github.com/Leon-Huang001208/ResearchWorkbench/blob/5a107ced93ec47f1fef0ed3f83830328c9907215/README.md#许可证)

## 保留原有条款

- `vendor/` 内随包组件使用各自的声明，包括 [CJPY Apache-2.0](vendor/cjpy/0.5.2/LICENSE) 和 [DSH Tabbit MIT](vendor/dsh-tabbit/0.3.4/LICENSE)。
- `services/ai_news/vendor/` 保留 [AIHOT MIT 和版权声明](services/ai_news/vendor/aihot/LICENSE)及其随包材料许可。`services/hot/`、`app/research_web/ui/hot-reader.css` 和 `app/research_web/ui/hot-reader.mjs` 中复用的 AIHOT 内容按[来源声明](services/hot/THIRD_PARTY_NOTICES.md)处理。两份 Web 混合文件整体排除，待厘清其中新旧材料的范围。
- `app/research_web/ui/vendor/` 和 `app/research_web/resources/fonts/` 保留各自的许可证，包括 [Chart.js MIT](app/research_web/ui/vendor/chart-js-4.4.7.LICENSE.txt)、[ECharts Apache-2.0](app/research_web/ui/vendor/echarts-5.5.0.LICENSE.txt)及 [Noto Sans SC 子集的 SIL OFL 1.1 声明](app/research_web/resources/fonts/OFL.txt)。
- `.agents/skills/` 及仓库其他位置内具有独立许可证、上游来源或第三方权利的材料，按对应来源和许可证处理。其中 [CLS Skill](.agents/skills/cls/LICENSE.txt) 和 [CNStock Skill](.agents/skills/cnstock/LICENSE.txt) 采用 CC BY-NC-SA 4.0，受原许可的非商业条件约束。

## 既有贡献与待核材料

`app/research_web/frameworks/embeds/` 整体排除，包括研究看板、构建产物、随包数据和资产。以下路径来自资讯雷达、看板接入和随包数据的三笔贡献，整份文件按排除处理，直至对混合内容完成逐项权属核对。排除是新许可范围说明。对尚未核实再分发权的材料，发行包须在取得授权或完成独立替换前排除。 [资讯雷达](https://github.com/Leon-Huang001208/ResearchWorkbench/commit/4e1d676b7) · [看板接入](https://github.com/Leon-Huang001208/ResearchWorkbench/commit/afdf253ea) · [随包数据](https://github.com/Leon-Huang001208/ResearchWorkbench/commit/6c1086209)

- `.ai/reports/2026-10-14-framework-direct-embed.md`
- `.ai/reports/intel-radar-20261009.md`
- `app/research_web/frameworks/embedded/__init__.py`
- `app/research_web/frameworks/embedded/collector.py`
- `app/research_web/frameworks/embedded/context.py`
- `app/research_web/frameworks/embedded/contracts.py`
- `app/research_web/frameworks/embedded/definition.py`
- `app/research_web/frameworks/embedded/seed.py`
- `app/research_web/frameworks/embedded/store.py`
- `app/research_web/frameworks/registry.py`
- `app/research_web/frameworks/scheduler.py`
- `app/research_web/intel_routes.py`
- `app/research_web/main.py`
- `app/research_web/ui/app.mjs`
- `app/research_web/ui/appearance.css`
- `app/research_web/ui/core.mjs`
- `app/research_web/ui/frameworks.mjs`
- `app/research_web/ui/frameworks/embedded.mjs`
- `app/research_web/ui/index.html`
- `app/research_web/ui/intel.css`
- `app/research_web/ui/intel.mjs`
- `app/research_web/ui/shell.mjs`
- `app/research_web/ui/styles.css`
- `docs/architecture/research-web/01-system.md`
- `docs/architecture/research-web/02-research-runtime.md`
- `docs/architecture/research-web/04-api.md`
- `docs/architecture/research-web/05-security-validation.md`
- `docs/architecture/research-web/08-research-frameworks.md`
- `docs/architecture/research-web/architecture-map.json`
- `docs/architecture/research-web/readme-review.json`
- `docs/generated/py_file_index.md`
- `docs/research-web-appearance.md`
- `docs/research-web-ui.md`
- `outputs/research-web-architecture/api-atlas.html`
- `outputs/research-web-architecture/index.html`
- `tests/javascript/research_web_intel.test.mjs`
- `tests/research_web/test_frameworks.py`
- `tests/research_web/test_intel.py`

README 中截至上述基线的既有内容排除在新许可之外。新增许可说明按新条款提供。

以 `Codex Local` 署名的既有贡献，其权属待确认。提交 `5e6b6d2c8` 对下列路径的历史内容排除在新许可之外。 [历史提交](https://github.com/Leon-Huang001208/ResearchWorkbench/commit/5e6b6d2c8)

- `.agents/project-constraints.json`
- `.ai/reports/2026-09-17-actions-quota-governance.md`
- `.github/workflows/project-constraints.yml`
- `.github/workflows/research-web-bootstrap.yml`
- `.github/workflows/research-web-checks.yml`
- `.github/workflows/research-web-windows-verify.yml`
- `AGENTS.md`
- `docs/CHANGELOG.md`
- `docs/DEVELOPMENT_MAP.md`
- `docs/README.md`
- `docs/actions-budget.md`
- `docs/architecture/research-web/06-documentation-contract.md`
- `docs/architecture/research-web/architecture-map.json`
- `docs/documentation-governance.json`
- `docs/research-web-documentation.md`
- `tests/javascript/actions_quota_governance.test.mjs`

## 发行包

此次许可变更适用于上述范围内的源码。现有全仓归档、Docker 镜像和 Python 发行包尚未按此范围完成审查。分发按新许可标注的产品包前，须核验包内每个待核材料的分发权，排除未取得所需权利的材料，并随包提供新许可和所有适用的第三方声明。当前 Docker 构建包含内嵌看板，源码工作树和默认构建产物均不能作为已核验的发行包。
