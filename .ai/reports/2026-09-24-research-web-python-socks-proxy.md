# Research Web Python SOCKS proxy bootstrap evidence

## Scope and boundary

This change fixes one existing bootstrap boundary: a fresh installer-owned Python environment cannot use a
`socks*://` proxy before a SOCKS transport is installed. Git keeps the host proxy environment because its
transport supports SOCKS. Python dependency installation and Corepack/Node retain only HTTP(S) proxy values,
using the same rule for upper- and lower-case variables. Filtering changes only the child-process environment,
logs only a bounded variable count, and neither changes the host environment nor records proxy values.

No dependency, public command, port, service, product route, persistent schema, or desktop path changes. Windows
automatic verification remains paused and is not claimed.

## Reproduction and TDD

On final master before this patch, a fresh installer-owned `.venv` with both
`ALL_PROXY=socks5://127.0.0.1:<port>` and `all_proxy=socks5://127.0.0.1:<port>` failed in the first locked pip
step with `Missing dependencies for SOCKS support` and stable outer code `python_install_step_1_failed`. Removing
only the upper-case variable reproduced the same failure because pip still read the lower-case value. Removing
both variables for the affected installer command completed the locked install without changing the system
proxy. The prior developer environment was preserved outside the checkout before this controlled reproduction.

The new focused test records every environment passed to Python dependency subprocesses. RED failed because
`HTTP_PROXY`, `http_proxy`, `ALL_PROXY`, and `all_proxy` still contained unsupported schemes. GREEN proves all
unsupported values are absent, HTTP(S) values remain, the base Git environment still contains SOCKS, and the
warning contains no proxy value. The full installation contract suite passed 31/31.

## Incremental validation

The fixed changed set contains ten paths: implementation, focused tests, four current documents, the generated
Python index, and these three evidence files. The project-local planner selected `full-delivery` / L4 with seven
local validation IDs and exactly three external gates: Project Constraints, Research Web Checks, and macOS
Bootstrap.

The first local attempt passed documentation governance, Python index, installation tests, and architecture
tests. Project Constraints then failed honestly with `reference_missing` because this report path was planned but
not yet created. The plan was regenerated with `validation_failure`; it remained L4 and retained the same local
and external closure. The final local results and receipt are recorded after rerunning the complete escalated
closure.

| Plan ID | Level | Result | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | L0 | passed; 502 files, 69 current, 0 violations | 0.165 s |
| `python-file-index` | L0 | passed; generated index verified | 0.829 s |
| `research-web-installation` | L1 | passed; 31/31 in 1.83 s | 2.688 s |
| `research-web-architecture` | L1 | passed; 62/62 | 2.254 s |
| `project-constraints-local` | L2 | passed; 10 paths, 0 violations | 0.114 s |
| `research-web-critical-smoke` | L3 | passed; 19/19 in 0.06 s | 0.801 s |
| `research-web-verification-full` | L4 | passed; 80/80 | 2.217 s |

The focused TDD run separately observed one expected RED failure before implementation and one GREEN pass after
the minimal change. The first pre-report local attempt is retained as failed evidence rather than relabeled:
documentation governance (0.156 s), Python index (1.006 s), installation contracts 31/31 (3.219 s), and
architecture 62/62 (2.306 s) passed; Project Constraints failed after 0.123 s with `reference_missing` for this
then-absent task report. No test, issue, or external gate was skipped to turn that attempt green.

The first static pass found only that Black would reformat `tests/research_web/test_setup_web.py`; Ruff had already
passed. Black formatted that one owned test file, after which Ruff, Black check, isort check, the installation
suite, and `git diff --check` passed. The complete seven-item escalated closure above was then rerun on the
post-format state; its results, not the pre-format run, are the receipt values.

## Architecture review

The proxy compatibility filter stays inside the existing public installer and does not add or reconnect any
Research Web runtime component.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"The installer changes only the allowlisted environment passed to Python dependency subprocesses; Web Host, DSH, API, service, and process relationships remain unchanged.","diagrams":[]} -->

## Merged macOS acceptance

Integration commit `6df3113e7c2237c2900231c3d1322488a7e552ad` passed the complete seven-item L4 local closure. Its worktree
started without `.venv`; the public `setup-web.sh --no-start` command ran with both upper- and lower-case
`ALL_PROXY=socks5://127.0.0.1:<port>` set and completed without manually unsetting either value. The setup log
contained `setup_web_python_proxy_protocol_filtered` and contained neither the proxy URL nor SOCKS scheme.

Stopped-state Doctor returned `ok: true` with an installer-owned Python 3.12.13 environment, matching lock,
`cjpy==0.5.2`, verified DSH closure and both services stopped. `rwb web start --no-open`, status, and running-state
Doctor then reported healthy 3081/8088 services. `rwb web stop` returned both services to stopped state.

## External evidence

The published integration SHA triggered exactly three automatic runs, all passed:

| Gate | Run | Result |
| --- | --- | --- |
| Project Constraints | [35941999113](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35941999113) | passed |
| Research Web Checks | [35941999116](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35941999116) | passed |
| Research Web Bootstrap | [35941999002](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35941999002) | passed |

Bootstrap contained exactly one job, `Clean Web install (macos-14)`, and completed setup, environment/service
verification, stop, and successful evidence upload. There was no Windows run. Windows remains explicitly unrun
and unclaimed under the user's manual-Windows boundary.
