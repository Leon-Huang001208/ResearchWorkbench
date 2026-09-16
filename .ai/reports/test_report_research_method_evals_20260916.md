# Test Report: Research Method Evals 20260916

## Task

- Task ID: `dc44e3f3-762c-46c9-9e95-8680e7e6c08a`
- Task name: 激活 Method UI 并运行独立 Research Evals
- Date: 2026-09-16
- Branch: `codex/dc44e3f3-762c-46c9-9e95-8680e7e6c08a-dc44e3f3-762c-46c9-9e95-8680e7e6c08a`

## Deployment And UI Evidence

- Deployment commit: `61fd1e3c17a5233b6c3a9515bfe8e76d96c78686`
- DSH 3081 PID at activation: `38445`
- Web 8088 PID at activation: `38515`
- Runtime API returned `connected=true` and `health_check_passed=true`.
- Method capability API returned 10 read-only `kind=method` capabilities.
- 2026-09-16 recheck confirmed the same PIDs and deployment cwd, 50 retained sessions, no `running`,
  `awaiting_approval` or `disconnected` session, and the specified interrupted record still present.
- Browser acceptance covered the fifth “方法” tab, method detail/source/business links, 1/3–3/3 selection,
  disabled fourth selection, keyboard tab navigation, Escape focus restoration, Light/Dark, 1440×1000 and
  390×844. Console errors/warnings were zero; observed network requests returned 200; mobile horizontal
  scroll width equaled the 390 px viewport.
- Evidence directory: `output/playwright/method-ui/.playwright-cli/` (ignored local evidence).
- Rollback deployment `93256dbb` remains present; the interrupted historical session was retained.

## Changed Source Files

- `benchmarks/research_methods.py`
- `benchmarks/datasets/research_methods_v1.jsonl`
- `core/model_gateway/providers/openai_compatible.py`

## Changed Test Files

- `tests/unit/test_research_method_benchmark.py`
- `tests/unit/core/model_gateway/test_openai_compatible_provider.py`

## Changed Documentation Files

- `benchmarks/FORMAT.md`
- `docs/architecture/research-web/07-capabilities.md`
- `docs/CHANGELOG.md`
- `.ai/reports/test_report_research_method_evals_20260916.md`

## Commands Run And Current Results

| Check | Result | Notes |
| --- | --- | --- |
| Target pytest | pass | shared provider, runner, structured output and Method routing focused run: 29 passed |
| Target Ruff | pass | `All checks passed!` |
| Target Black | pass | 4 files unchanged |
| Target isort | pass | no output, exit 0 |
| JavaScript Method tests | pass | 39/39; capability UI plus Method catalog/selection/preview/retry and bounded method-use tool |
| Mypy (changed sources) | pass | `--follow-imports=silent`; no issues in 2 source files |
| Architecture gate | pass | no violations |
| Project constraints | pass | no violations |
| Task completion / doc sync | pass | task report present; no doc-sync violations |
| Real eval v1 | failed closed | 0/63; minimal `.venv` lacked optional OpenAI SDK, so the old gateway returned a non-model placeholder |
| Real eval v2 | failed closed | 0/63; direct request reached `api.deepseek.com` and received HTTP 401; no candidate produced |
| Real eval v3 | failed closed | 0/63; direct adapter reached the model, but accepted non-final reasoning text as content |
| Real eval r4 | failed closed | 0/63; shared gateway worked, but the textual output contract used an inconsistent `source_tier` name |
| Real eval r5 | failed closed | 8/63; exact schema fixed field validity, then one response hit the 4096 output-token ceiling |
| Real eval r6 | pass | 63/63 with `deepseek-v4-pro`; only `dual-layer-explanation` is a manual-review candidate |
| Full Research Web regression, attempt 1 | environment failure | inherited SOCKS proxy required absent `socksio`; 70 passed before stop |
| Full Research Web regression, attempt 2 | incomplete baseline | proxy-cleared run reached 242 passed/2 skipped; existing CLI lazy-help subprocess timed out and the following test stalled, so the run was stopped |
| Delivery/CI | pending | Results will be appended after integration publication |

## Privacy And Scope

- No dependency was added.
- The three reference Markdown files and report-project `prompt_templates.md` were not modified.
- Raw model output is configured for `~/.research-workbench/research-evals/<run-id>/` with private modes;
  tracked results omit Prompt, evidence text and model response bodies.
- The runner does not call the Research Web product API, UI or engineering Harness; it reuses the same
  in-process `ModelGatewayImpl` and `TASK_REASONING` route as the product.
- Promotion candidates are review inputs only and do not change `method_policy.recommended`.
- r6 used only the configured DeepSeek provider and `deepseek-v4-pro`; no alternate provider was selected and no
  credential was modified. The private r6 directory contains 63 files with directory mode `0700` and file mode
  `0600`; the tracked JSON/Markdown contain no Prompt, messages, evidence text or response content.

## Known Baseline Limitation

- Direct mypy with full import traversal reports 13 pre-existing errors in `core/observability/tracer.py` and
  `core/observability/metrics.py` for structured logger keyword arguments. Those files are unchanged by this task.
  `mypy --follow-imports=silent benchmarks/research_methods.py` passes for the new runner itself.

## Final Decision

- [x] Local implementation and evidence are safe to deliver.
- [ ] Delivery completion still requires commit, merged-result verification, publication, conclusive CI and cleanup.
