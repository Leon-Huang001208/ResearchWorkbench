# Research Workbench Native + Docker Dual Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-grade Docker runtime beside the existing Native Research Web runtime, with one source/dependency/data model, a unified `rwb` CLI, safe switching, truthful diagnostics, conditional CI, and preserved Native defaults.

**Architecture:** A stdlib-only host bootstrap reads a private runtime-mode record before any `.venv` import and routes Web lifecycle commands to either the existing Native manager or a Compose controller. Docker runs DSH and FastAPI in one container so DSH keeps its loopback/auth boundary; canonical research data and DSH history are shared sequentially, while PID/container/auth/overlay/build evidence is runtime-specific. A machine-readable runtime contract supplies Native and Docker with the same Python, Node, CJPY, DSH and pnpm facts.

**Tech Stack:** Python 3.12, Click, FastAPI/Uvicorn, DSH/Node 24/Corepack/pnpm, Docker BuildKit and Compose v2, POSIX shell and Windows batch launchers, pytest, Node test runner, GitHub Actions, ResearchWorkbench verification planner/receipt/Harness.

---

## File map

### Runtime contract and host bootstrap

- Create `runtimes/research_web.json`: machine source of truth for Python, Node, CJPY, DSH and pnpm runtime facts.
- Create `app/research_web/runtime_contract.py`: strict production loader for the machine contract.
- Create `research_workbench_entrypoint/runtime_mode.py`: stdlib-only private mode record and installation identity store.
- Create `research_workbench_entrypoint/docker_runtime.py`: stdlib-only Docker/Compose controller.
- Create `research_workbench_entrypoint/bootstrap.py`: stdlib-only `runtime` and Docker-mode `web` command parser/delegator.
- Modify `research_workbench_entrypoint/__init__.py`: enter the bootstrap before importing Click.
- Modify `rwb`, `rwb.cmd`: select host Python 3.12 for bootstrap without requiring `.venv`; preserve Native delegation.

### Shared process lifecycle and container runtime

- Create `app/research_web/process_spec.py`: shared DSH/Web command specification with explicit data/state/host parameters.
- Modify `app/research_web/service_manager.py`: consume shared process specs and accept a separate runtime-state root while preserving Native defaults.
- Modify `app/research_web/launch_runtime.py`: accept `--state`, store auth-adjacent generated state outside canonical DSH home, and load the machine runtime contract.
- Modify `app/research_web/client.py`: continue using `RESEARCH_RUNTIME_AUTH`; no mode branching.
- Create `docker/entrypoint.sh`: validate required mounts and `exec` the supervisor.
- Create `docker/supervisor.py`: PID 1 signal-aware DSH→Web supervisor using shared process specs/health.
- Create `docker/healthcheck.py`: authenticated DSH plus Web health probe.
- Create `Dockerfile`, `compose.yaml`, `.dockerignore`: fixed multi-stage, non-root, single-container packaging.

### Installation, secrets, Doctor and CLI

- Modify `scripts/setup_web.py`: runtime-aware Native/Docker installers, preflight, install summaries and `--runtime`.
- Create `app/research_web/credential_backend.py`: private file keyring-compatible backend selected only in Docker.
- Modify `app/research_web/datahub/connections.py`, `mcp_registry/credentials.py`, `mcp_runtime/credentials.py`, `automation/channels.py`, `mcp_runtime/installation_store.py`, and `service.py`: obtain a shared backend factory instead of independently importing the system keyring.
- Modify `app/cli/main.py`: retain Native Click behavior and additive logs/status JSON contracts.
- Modify `app/research_web/main.py`: compose the Docker credential backend from the non-secret credential-root setting.

### Verification and documentation

- Modify `.agents/verification-policy.json`, `scripts/plan_verification.mjs` only if schema behavior is required, and policy contract tests.
- Create `.github/workflows/research-web-docker.yml`; modify quota-governance tests and `docs/actions-budget.md`.
- Modify `README.md`, installation/architecture/development/workflow/security docs, architecture map/diagram receipts and README review receipt.
- Create `.ai/reports/2026-09-29-native-docker-dual-runtime-*` plan, receipt and evidence artifacts.

### Tests

- Create `tests/research_web/test_runtime_contract.py`.
- Create `tests/research_web/test_runtime_mode.py`.
- Create `tests/research_web/test_docker_runtime.py`.
- Create `tests/research_web/test_container_supervisor.py`.
- Create `tests/research_web/test_credential_backend.py`.
- Modify `tests/research_web/test_service_manager.py`, `test_runtime_launch.py`, `test_setup_web.py`, `test_cli_lazy.py`, connection/MCP/automation credential tests.
- Create `tests/javascript/docker_runtime_contract.test.mjs`.
- Modify `tests/javascript/verification_policy.test.mjs`, `actions_quota_governance.test.mjs`, architecture/documentation tests where required.

## Task 0: Commit the reviewed implementation plan

**Files:**
- Create: `docs/superpowers/plans/2026-09-29-native-docker-dual-runtime.md`

- [ ] **Step 1: Validate the plan document**

Run:

```bash
/opt/homebrew/bin/python3.12 - <<'PY'
from pathlib import Path

path = Path("docs/superpowers/plans/2026-09-29-native-docker-dual-runtime.md")
text = path.read_text(encoding="utf-8")
markers = ["T" + "BD", "T" + "ODO", "implement" + " later", "fill" + " in details", "待" + "定"]
found = [marker for marker in markers if marker in text]
raise SystemExit(f"deferred markers: {found}" if found else 0)
PY
git diff --check
node scripts/check_documentation_governance.mjs --project .
/opt/homebrew/bin/python3.12 scripts/generate_py_file_index.py --check
```

Expected: `rg` finds no placeholders, diff check is clean, governance has `violations: []`, and the Python index is verified.

- [ ] **Step 2: Commit the plan**

```bash
git add docs/superpowers/plans/2026-09-29-native-docker-dual-runtime.md
git commit -m "docs: plan native and docker runtime delivery"
```

Expected: the isolated branch contains the reviewed design commit followed by this plan commit; no implementation file is changed.

## Task 1: Register Docker/runtime paths in Minimal Acceptance before implementation

**Files:**
- Modify: `.agents/verification-policy.json`
- Modify: `tests/javascript/verification_policy.test.mjs`
- Create: `tests/javascript/docker_runtime_contract.test.mjs`
- Modify: `tests/javascript/incremental_validation_skill.test.mjs`

- [ ] **Step 1: Write RED policy contracts for every new boundary**

Add catalogs with these exact IDs and commands:

```json
{
  "research-web-runtime-mode": {
    "level": "L1",
    "execution": "local",
    "value": "python -m pytest tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py --confcutdir=tests/research_web"
  },
  "research-web-container-runtime": {
    "level": "L2",
    "execution": "local",
    "value": "python -m pytest tests/research_web/test_container_supervisor.py tests/research_web/test_runtime_launch.py --confcutdir=tests/research_web"
  },
  "research-web-docker-contract": {
    "level": "L2",
    "execution": "local",
    "value": "node --test tests/javascript/docker_runtime_contract.test.mjs"
  },
  "research-web-credential-backend": {
    "level": "L2",
    "execution": "local",
    "value": "python -m pytest tests/research_web/test_credential_backend.py --confcutdir=tests/research_web"
  }
}
```

Add a Docker external gate:

```json
"research-web-docker": {
  "level": "L4",
  "execution": "external",
  "value": ".github/workflows/research-web-docker.yml#docker-runtime"
}
```

Add tests that probe these complete changed sets and assert no `unknown_path`, no desktop gates, and the expected Docker gate:

```javascript
const dockerPackaging = success(run(repositoryRoot, [
  "Dockerfile", "compose.yaml", ".dockerignore", "docker/entrypoint.sh",
  "docker/supervisor.py", "docker/healthcheck.py",
]));
assert.equal(dockerPackaging.reasons.some(item => item.code === "unknown_path"), false);
assert.equal(dockerPackaging.requiredLevel, "L4");
assert.equal(dockerPackaging.receiptTemplate.externalGateIds.includes("research-web-docker"), true);
assert.equal(dockerPackaging.receiptTemplate.externalGateIds.includes("native-windows-desktop"), false);

const runtimeRouter = success(run(repositoryRoot, [
  "research_workbench_entrypoint/runtime_mode.py",
  "research_workbench_entrypoint/docker_runtime.py",
  "research_workbench_entrypoint/bootstrap.py",
  "tests/research_web/test_runtime_mode.py",
  "tests/research_web/test_docker_runtime.py",
]));
assert.equal(runtimeRouter.reasons.some(item => item.code === "unknown_path"), false);
assert.equal(runtimeRouter.tests.some(item => item.id === "research-web-runtime-mode"), true);
```

- [ ] **Step 2: Run RED tests**

```bash
node --test tests/javascript/verification_policy.test.mjs \
  tests/javascript/incremental_validation_skill.test.mjs
```

Expected: new assertions fail because Docker/runtime files currently route to fallback and the catalogs/gate do not exist.

- [ ] **Step 3: Add narrow production rules**

Add four rules rather than broadening generic Research Web matching:

```json
{
  "id": "research-web-docker-packaging",
  "risk": "full-delivery",
  "minimumLevel": "L4",
  "reason": "research_web_docker_packaging_change",
  "impact": ["docker-runtime", "web-installation"],
  "coupling": "high",
  "match": {
    "files": ["Dockerfile", "compose.yaml", ".dockerignore"],
    "prefixes": ["docker/"],
    "segments": [],
    "suffixes": []
  },
  "tests": ["research-web-docker-contract", "research-web-container-runtime", "research-web-architecture", "project-constraints-local", "research-web-verification-full"],
  "documentation": ["documentation-governance", "python-file-index"],
  "ci": ["project-constraints", "research-web-checks", "research-web-docker"]
}
```

Add corresponding exact rules for `runtimes/research_web.json` + `runtime_contract.py`, the three bootstrap/controller modules + their tests, and the credential backend + its tests. Runtime/setup/CI production files remain L4; isolated test-only changes may stay at their catalog level.

- [ ] **Step 4: Run GREEN tests and planner probes**

```bash
node --test tests/javascript/verification_policy.test.mjs \
  tests/javascript/incremental_validation_skill.test.mjs
node scripts/plan_verification.mjs --project . \
  --changed-file Dockerfile \
  --changed-file compose.yaml \
  --changed-file .dockerignore \
  --changed-file docker/entrypoint.sh \
  --changed-file docker/supervisor.py \
  --changed-file docker/healthcheck.py
node scripts/plan_verification.mjs --project . \
  --changed-file research_workbench_entrypoint/runtime_mode.py \
  --changed-file research_workbench_entrypoint/docker_runtime.py \
  --changed-file research_workbench_entrypoint/bootstrap.py \
  --changed-file tests/research_web/test_runtime_mode.py \
  --changed-file tests/research_web/test_docker_runtime.py
```

Expected: no unknown paths; Docker packaging is L4 with Docker CI; runtime router selects its focused tests and full-delivery without desktop gates.

- [ ] **Step 5: Commit verification routing**

```bash
git add .agents/verification-policy.json \
  tests/javascript/verification_policy.test.mjs \
  tests/javascript/incremental_validation_skill.test.mjs \
  tests/javascript/docker_runtime_contract.test.mjs
git commit -m "ci: route dual runtime verification"
```

## Task 2: Centralize the Native/Docker runtime contract

**Files:**
- Create: `runtimes/research_web.json`
- Create: `app/research_web/runtime_contract.py`
- Create: `tests/research_web/test_runtime_contract.py`
- Modify: `scripts/setup_web.py`
- Modify: `app/research_web/__init__.py`
- Modify: `app/research_web/launch_runtime.py`
- Modify: `tests/research_web/test_setup_web.py`
- Modify: `tests/research_web/test_runtime_launch.py`

- [ ] **Step 1: Write failing strict-loader and parity tests**

Use this contract shape in the test fixture:

```python
EXPECTED = {
    "schema_version": 1,
    "python": {"major": 3, "minor": 12, "docker_image": "python:3.12.13-slim-bookworm"},
    "node": {"major": 24, "minimum_minor": 0, "docker_image": "node:24.19.0-bookworm-slim"},
    "cjpy": {"version": "0.5.2", "sha256": "d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94"},
    "dsh": {
        "remote": "https://github.com/Leon-Huang001208/deepseek-harness.git",
        "commit": "c919b2a460753859665db3f60143d525fb9140cf",
        "pnpm": "11.7.0",
        "closure_files": 11084,
    },
}
```

Tests must reject extra keys, wrong types, unsupported Python/Node values, malformed URLs/hashes and aliased contract paths. Assert existing exported constants equal the loaded contract during migration.

- [ ] **Step 2: Run RED tests**

```bash
python -m pytest tests/research_web/test_runtime_contract.py \
  tests/research_web/test_setup_web.py::test_runtime_constants_share_the_machine_contract \
  tests/research_web/test_runtime_launch.py::test_runtime_constants_share_the_machine_contract \
  --confcutdir=tests/research_web
```

Expected: import/file failures because the contract and loader do not exist.

- [ ] **Step 3: Implement the strict loader**

Expose an immutable dataclass with the fields below. The production function
`load_runtime_contract(path: Path | None = None) -> ResearchWebRuntimeContract`
must return a fully validated instance or raise `RuntimeContractError`:

```python
@dataclass(frozen=True, slots=True)
class ResearchWebRuntimeContract:
    python_major: int
    python_minor: int
    python_docker_image: str
    node_major: int
    node_minimum_minor: int
    node_docker_image: str
    cjpy_version: str
    cjpy_sha256: str
    dsh_remote: str
    dsh_commit: str
    dsh_pnpm: str
    dsh_closure_files: int
```

The implementation must use bounded UTF-8 reading, exact key sets, regular-file/alias checks, explicit type checks and stable `RuntimeContractError` codes. Replace duplicated constants in installer/runtime modules with values from one loaded contract while retaining compatibility exports.

- [ ] **Step 4: Run GREEN tests and import guard**

```bash
python -m pytest tests/research_web/test_runtime_contract.py \
  tests/research_web/test_setup_web.py \
  tests/research_web/test_runtime_launch.py \
  --confcutdir=tests/research_web
python -c "import app.research_web.service_manager; assert 'app.research_web.launch_runtime' not in __import__('sys').modules"
```

Expected: all pass; the lightweight service-manager import still does not load the runtime feature graph.

- [ ] **Step 5: Commit the contract**

```bash
git add runtimes/research_web.json app/research_web/runtime_contract.py \
  app/research_web/__init__.py app/research_web/launch_runtime.py scripts/setup_web.py \
  tests/research_web/test_runtime_contract.py tests/research_web/test_setup_web.py \
  tests/research_web/test_runtime_launch.py
git commit -m "refactor: centralize research web runtime contract"
```

## Task 3: Add the stdlib runtime-mode store

**Files:**
- Create: `research_workbench_entrypoint/runtime_mode.py`
- Create: `tests/research_web/test_runtime_mode.py`

- [ ] **Step 1: Write RED tests for compatibility and private storage**

Cover these exact outcomes:

```python
assert RuntimeModeStore(home).read().mode == "native"  # missing file compatibility
record = RuntimeModeStore(home).write("docker")
assert record.mode == "docker"
assert re.fullmatch(r"[a-f0-9]{32}", record.installation_id)
assert stat.S_IMODE((home / "install/runtime.json").stat().st_mode) == 0o600
```

Also test stable rejection of invalid JSON, extra keys, unknown mode, changed installation ID, symlinked file/parent, Windows reparse-point simulation, oversized input and atomic-write cleanup.

- [ ] **Step 2: Run RED tests**

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/research_web/test_runtime_mode.py \
  --confcutdir=tests/research_web
```

Expected: module import fails.

- [ ] **Step 3: Implement a stdlib-only store**

Use the `RuntimeMode` literal and immutable `RuntimeModeRecord` below without
importing `app`, Click or third-party modules. `RuntimeModeStore.read()` returns
`RuntimeModeRecord`; `RuntimeModeStore.write(mode)` returns the persisted
`RuntimeModeRecord`:

```python
RuntimeMode = Literal["native", "docker"]

@dataclass(frozen=True, slots=True)
class RuntimeModeRecord:
    schema_version: int
    mode: RuntimeMode
    installation_id: str
    updated_at: str | None
```

Missing file returns a synthetic Native record without writing. First write generates one installation ID; later writes preserve it. All exceptions expose stable non-path `RuntimeModeError.code` while logs contain only operation/code.

- [ ] **Step 4: Run GREEN tests and stdlib import audit**

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/research_web/test_runtime_mode.py \
  --confcutdir=tests/research_web
/opt/homebrew/bin/python3.12 -I -c \
  "import sys; sys.path.insert(0,'.'); import research_workbench_entrypoint.runtime_mode; assert 'click' not in sys.modules"
```

Expected: pass; Click/FastAPI/structlog are absent.

- [ ] **Step 5: Commit mode storage**

```bash
git add research_workbench_entrypoint/runtime_mode.py tests/research_web/test_runtime_mode.py
git commit -m "feat: persist research web runtime mode"
```

## Task 4: Separate process specification from Native ownership state

**Files:**
- Create: `app/research_web/process_spec.py`
- Modify: `app/research_web/service_manager.py`
- Modify: `app/research_web/launch_runtime.py`
- Modify: `tests/research_web/test_service_manager.py`
- Modify: `tests/research_web/test_runtime_launch.py`

- [ ] **Step 1: Write RED tests for data/state/host separation**

Assert Native defaults remain byte-for-byte compatible and Docker parameters differ only where intended:

```python
native = build_process_specs(
    python="/venv/python", node="/node", project_root=root,
    data_root=data, runtime_source=dsh, state_root=data / "runtime",
    web_host="127.0.0.1", web_port=8088, runtime_port=3081,
)
assert "127.0.0.1" in native.web.command
assert native.runtime_state_root == data / "runtime"

container = build_process_specs(
    python="/opt/rwb/bin/python", node="/usr/local/bin/node", project_root=root,
    data_root=Path("/data/research-web"), runtime_source=Path("/opt/rwb/dsh"),
    state_root=Path("/state"), web_host="0.0.0.0", web_port=8088, runtime_port=3081,
)
assert "0.0.0.0" in container.web.command
assert "--state" in container.runtime.command
assert container.runtime.signature[1] == "/state/overlay.yml"
```

Add launch tests proving `DSH_HOME == data/runtime/home`, while overlay/build lock are under `state_root` and auth path comes from `RESEARCH_RUNTIME_AUTH`.

- [ ] **Step 2: Run RED tests**

```bash
python -m pytest tests/research_web/test_service_manager.py \
  tests/research_web/test_runtime_launch.py --confcutdir=tests/research_web
```

Expected: missing process-spec API and `--state` support failures.

- [ ] **Step 3: Implement shared specs and backward-compatible state root**

Define immutable specs:

```python
@dataclass(frozen=True, slots=True)
class ProcessSpec:
    role: Literal["runtime", "web"]
    port: int
    command: tuple[str, ...]
    signature: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class WebProcessSpecs:
    runtime: ProcessSpec
    web: ProcessSpec
    runtime_state_root: Path
```

`WebServiceManager(runtime_state_root=None)` must default to `data_root/runtime`. Existing Native state, auth, overlay, build-lock and formatting tests must continue passing. `launch_runtime --state` defaults to `<data>/runtime` when omitted so direct historical invocations remain valid.

- [ ] **Step 4: Run GREEN focused tests**

```bash
python -m pytest tests/research_web/test_service_manager.py \
  tests/research_web/test_runtime_launch.py --confcutdir=tests/research_web
```

Expected: all existing and new tests pass.

- [ ] **Step 5: Commit process boundary**

```bash
git add app/research_web/process_spec.py app/research_web/service_manager.py \
  app/research_web/launch_runtime.py tests/research_web/test_service_manager.py \
  tests/research_web/test_runtime_launch.py
git commit -m "refactor: separate web process data and state"
```

## Task 5: Build the container supervisor and healthcheck

**Files:**
- Create: `docker/entrypoint.sh`
- Create: `docker/supervisor.py`
- Create: `docker/healthcheck.py`
- Create: `tests/research_web/test_container_supervisor.py`

- [ ] **Step 1: Write RED supervisor tests with real child fixtures**

Use short Python subprocess fixtures, not mocked success, to prove:

- DSH starts before Web;
- Web is never started when DSH health fails;
- Web start failure terminates DSH;
- SIGTERM stops Web then DSH and exits zero;
- unexpected child exit terminates the sibling and exits nonzero;
- escalation to SIGKILL occurs only after the configured grace period;
- logs contain role/state/error code but not environment values or auth Cookie.

The supervisor dependency boundary is:

```python
@dataclass(frozen=True, slots=True)
class SupervisorConfig:
    data_root: Path
    state_root: Path
    project_root: Path
    runtime_source: Path
    python: str
    node: str
    web_port: int = 8088
    runtime_port: int = 3081
    startup_timeout: float = 35.0
    shutdown_timeout: float = 8.0
```

The production entry `run(config: SupervisorConfig, *, probe: HealthProbe =
real_probe) -> int` returns zero only after an orderly external shutdown; startup
failure or unexpected child exit returns nonzero after sibling cleanup.

- [ ] **Step 2: Run RED tests**

```bash
python -m pytest tests/research_web/test_container_supervisor.py \
  --confcutdir=tests/research_web
```

Expected: missing supervisor/health modules.

- [ ] **Step 3: Implement PID 1 behavior and entrypoint**

`docker/entrypoint.sh` must be exactly a validation/exec wrapper:

```sh
#!/bin/sh
set -eu
: "${RWB_DATA_ROOT:=/data/research-web}"
: "${RWB_RUNTIME_STATE:=/state}"
test -d "$RWB_DATA_ROOT" && test -w "$RWB_DATA_ROOT"
test -d "$RWB_RUNTIME_STATE" && test -w "$RWB_RUNTIME_STATE"
exec /opt/rwb/venv/bin/python /opt/rwb/docker/supervisor.py
```

Supervisor uses argument arrays, process groups, bounded probes and signal handlers; it never shells out through a command string. `healthcheck.py` reads only the bounded auth record and calls DSH `session/list` plus Web `/api/research/runtime`, returning 0 only when both pass.

- [ ] **Step 4: Run GREEN tests and shell syntax**

```bash
python -m pytest tests/research_web/test_container_supervisor.py \
  --confcutdir=tests/research_web
/bin/sh -n docker/entrypoint.sh
```

Expected: all pass.

- [ ] **Step 5: Commit supervisor**

```bash
git add docker/entrypoint.sh docker/supervisor.py docker/healthcheck.py \
  tests/research_web/test_container_supervisor.py
git commit -m "feat: supervise web services inside docker"
```

## Task 6: Add Dockerfile, Compose and packaging contracts

**Files:**
- Create: `Dockerfile`
- Create: `compose.yaml`
- Create: `.dockerignore`
- Modify: `tests/javascript/docker_runtime_contract.test.mjs`

- [ ] **Step 1: Write RED static packaging tests**

Parse files as text/YAML-safe structures and assert:

```javascript
assert.match(dockerfile, /^# syntax=docker\/dockerfile:1/m);
assert.match(dockerfile, /--require-hashes[^\n]*requirements\/web\.lock/);
assert.match(dockerfile, /pnpm@11\.7\.0[^\n]*--frozen-lockfile/);
assert.match(dockerfile, /USER rwb/);
assert.doesNotMatch(dockerfile, /COPY \. \/|ARG .*KEY|ENV .*KEY/);
assert.match(compose, /127\.0\.0\.1:\$\{RWB_WEB_PORT:-8088\}:8088/);
assert.doesNotMatch(compose, /3081:3081|RESEARCH_DSH_API_KEY:/);
```

Also assert `.dockerignore` excludes `.git`, all `.venv*`, `.worktrees`, logs, `.ai/reports`, caches, credentials, runtime data and local env files while allowing the exact runtime/application/vendor/requirements files used by the image.

- [ ] **Step 2: Run RED packaging test**

```bash
node --test tests/javascript/docker_runtime_contract.test.mjs
```

Expected: missing packaging files.

- [ ] **Step 3: Implement the fixed multi-stage image**

Use this stage sequence:

```dockerfile
# syntax=docker/dockerfile:1
ARG NODE_IMAGE=node:24.19.0-bookworm-slim
ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm
FROM ${NODE_IMAGE} AS node-runtime
FROM ${PYTHON_IMAGE} AS python-builder
FROM python-builder AS dsh-builder
FROM ${PYTHON_IMAGE} AS runtime
```

`python-builder` installs `requirements/web.lock --require-hashes`, the local project and vendored CJPY into `/opt/rwb/venv`. `dsh-builder` obtains only the contract-pinned repository/commit, runs pinned Corepack/pnpm frozen install/build, verifies closure via the project helper, and publishes `/opt/rwb/dsh`. The final stage copies Node/Corepack, venv, source and DSH closure, creates fixed non-root `rwb`, declares volumes, healthcheck and entrypoint.

Compose must have one `research-web` service, no database, `init: false` because the Python supervisor is PID 1, a read-only root filesystem with explicit writable mounts/tmpfs where feasible, loopback-only Web publishing, canonical data bind, runtime-state bind, credential bind, stable labels and no secret-valued environment.

- [ ] **Step 4: Run GREEN static tests and Compose validation when available**

```bash
node --test tests/javascript/docker_runtime_contract.test.mjs
if command -v docker >/dev/null 2>&1; then docker compose -f compose.yaml config --quiet; fi
```

Expected: static contracts pass. On this host the Docker command is currently absent, so Compose validation must be recorded `not_run`, not passed.

- [ ] **Step 5: Commit Docker packaging**

```bash
git add Dockerfile compose.yaml .dockerignore tests/javascript/docker_runtime_contract.test.mjs
git commit -m "feat: package research web docker runtime"
```

## Task 7: Implement the stdlib Docker controller and safe mode switch

**Files:**
- Create: `research_workbench_entrypoint/docker_runtime.py`
- Create: `research_workbench_entrypoint/bootstrap.py`
- Modify: `research_workbench_entrypoint/__init__.py`
- Modify: `rwb`
- Modify: `rwb.cmd`
- Create: `tests/research_web/test_docker_runtime.py`
- Modify: `tests/research_web/test_runtime_mode.py`
- Modify: `tests/research_web/test_cli_lazy.py`

- [ ] **Step 1: Write RED controller/launcher tests**

Use a recording subprocess runner and real loopback sockets to cover:

```python
controller = DockerRuntime(project_root, home, runner=runner)
assert controller.compose_prefix == (
    "docker", "compose", "--project-name", f"rwb-{installation_id[:12]}",
    "--project-directory", str(project_root), "-f", str(project_root / "compose.yaml"),
)
```

Test distinct codes for missing CLI, daemon, Compose, unsupported architecture, unsafe home, foreign labels, unavailable image and occupied ports. Test `runtime use docker` preflights target before stopping Native, refuses a running runtime without `--stop-current`, stops only owned state, waits for both ports, atomically writes the mode, and does not auto-start the target.

Launcher subprocess tests must prove Docker `runtime status` and `web status` work with no `.venv`, while Native/legacy commands still use the exact existing `.venv` entrypoint and preserve argv/exit code.

- [ ] **Step 2: Run RED tests**

```bash
/opt/homebrew/bin/python3.12 -m pytest \
  tests/research_web/test_runtime_mode.py \
  tests/research_web/test_docker_runtime.py \
  tests/research_web/test_cli_lazy.py \
  --confcutdir=tests/research_web
```

Expected: missing controller/bootstrap behavior.

- [ ] **Step 3: Implement controller and bootstrap**

Expose `DockerRuntime.preflight/install/start/stop/restart/status/doctor/logs`
with the signatures specified by the tests in Step 1. Lifecycle and diagnostic
methods return structured dictionaries; `logs(follow, tail)` returns the Compose
process exit code after streaming or bounded capture.

All subprocess calls use arrays, exact cwd/environment, timeout and captured output caps. Compose environment contains only non-secret project/data/state/credential paths, installation ID and ports. Status/Doctor inspect only allowlisted fields and verify exact labels.

Bootstrap owns a small argparse parser for `runtime` and Docker-mode `web`; it delegates everything else by `os.execve` to `.venv` with current project root/PYTHONPATH and existing Node selection. JSON output never mixes logs on stdout.

- [ ] **Step 4: Run GREEN tests and launcher smoke**

```bash
/opt/homebrew/bin/python3.12 -m pytest \
  tests/research_web/test_runtime_mode.py \
  tests/research_web/test_docker_runtime.py \
  tests/research_web/test_cli_lazy.py \
  --confcutdir=tests/research_web
tmp_home="$(mktemp -d)"
HOME="$tmp_home" ./rwb runtime status --json
```

Expected: tests pass; a missing mode record reports Native without writing or requiring `.venv` for `runtime status`.

- [ ] **Step 5: Commit unified routing**

```bash
git add research_workbench_entrypoint/runtime_mode.py \
  research_workbench_entrypoint/docker_runtime.py \
  research_workbench_entrypoint/bootstrap.py \
  research_workbench_entrypoint/__init__.py rwb rwb.cmd \
  tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py \
  tests/research_web/test_cli_lazy.py
git commit -m "feat: route rwb through native or docker runtime"
```

## Task 8: Integrate runtime selection into setup-web

**Files:**
- Modify: `scripts/setup_web.py`
- Modify: `setup-web.sh`
- Modify: `setup-web.cmd`
- Modify: `tests/research_web/test_setup_web.py`

- [ ] **Step 1: Write RED setup contracts**

Add parser and installer tests proving:

```python
assert parse_args([]).runtime == "native"
assert parse_args(["--runtime", "native"]).runtime == "native"
assert parse_args(["--runtime", "docker", "--no-start"]).runtime == "docker"
```

Use temporary projects and a recording Docker controller to assert Docker mode never calls `prepare_environment`, never creates/replaces `.venv`, writes `install/docker-manifest.json` only after successful build, respects `--check-only`, `--repair`, `--no-start`, and prints path-free JSON. Test all stable detection codes and that Native mode output/behavior remains unchanged.

- [ ] **Step 2: Run RED setup tests**

```bash
python -m pytest tests/research_web/test_setup_web.py --confcutdir=tests/research_web
```

Expected: `--runtime` is unknown and Docker path is absent.

- [ ] **Step 3: Implement explicit runtime installation**

Refactor parser creation into a testable
`build_parser() -> argparse.ArgumentParser` function and dispatch with this
complete branch:

```python
def install_selected_runtime(arguments, *, project_root: Path) -> dict[str, object]:
    data_home = Path.home() / ".research-workbench"
    if arguments.runtime == "docker":
        return DockerRuntime(project_root, data_home).install(
            repair=arguments.repair,
            start=not arguments.no_start,
        )
    return SetupWebInstaller(project_root=project_root).install(
        repair=arguments.repair,
        start=not arguments.no_start,
    )
```

Wrappers continue forwarding all arguments unchanged. Docker errors print platform-specific remediation without installing Docker or changing daemon/system settings.

- [ ] **Step 4: Run GREEN setup and Native regression tests**

```bash
python -m pytest tests/research_web/test_setup_web.py \
  tests/research_web/test_cli_lazy.py --confcutdir=tests/research_web
/bin/sh -n setup-web.sh
```

Expected: pass; no-argument tests still prove Native compatibility.

- [ ] **Step 5: Commit setup integration**

```bash
git add scripts/setup_web.py setup-web.sh setup-web.cmd \
  tests/research_web/test_setup_web.py tests/research_web/test_cli_lazy.py
git commit -m "feat: install native or docker web runtime"
```

## Task 9: Add a Docker-only private credential backend

**Files:**
- Create: `app/research_web/credential_backend.py`
- Create: `tests/research_web/test_credential_backend.py`
- Modify: `app/research_web/datahub/connections.py`
- Modify: `app/research_web/mcp_registry/credentials.py`
- Modify: `app/research_web/mcp_runtime/credentials.py`
- Modify: `app/research_web/mcp_runtime/installation_store.py`
- Modify: `app/research_web/automation/channels.py`
- Modify: `app/research_web/service.py`
- Modify: relevant connection/MCP/automation tests

- [ ] **Step 1: Write RED backend security tests**

Test the keyring-compatible API:

```python
backend = PrivateFileCredentialBackend(root)
backend.set_password("ResearchWorkbench.Test", "account", "secret-value")
assert backend.get_password("ResearchWorkbench.Test", "account") == "secret-value"
backend.delete_password("ResearchWorkbench.Test", "account")
assert backend.get_password("ResearchWorkbench.Test", "account") is None
```

Assert `0700` root, `0600` records, hashed service/account filenames, bounded values, exact UTF-8 JSON, atomic replace, thread/process lock, no secret in filenames/logs/errors, readback verification, symlink/hardlink/reparse rejection and cleanup after failed writes. Add factory tests: absent `RESEARCH_CREDENTIAL_HOME` returns the system adapter; an absolute validated credential home returns the file backend; relative/unsafe values fail closed.

- [ ] **Step 2: Run RED credential tests**

```bash
python -m pytest tests/research_web/test_credential_backend.py \
  --confcutdir=tests/research_web
```

Expected: missing backend module.

- [ ] **Step 3: Implement and inject one backend factory**

Define a `CredentialBackend` Protocol with the existing keyring-compatible
`get_password`, `set_password` and `delete_password` signatures. Implement
`default_credential_backend() -> CredentialBackend` so explicit Docker file-root
configuration selects `PrivateFileCredentialBackend`; otherwise it returns the
system keyring adapter.

Replace each local `_SystemKeyring` default with this factory; explicit test injection still wins. Model API keys remain in DSH credentials and are not copied to this backend. Compose sets only `RESEARCH_CREDENTIAL_HOME=/run/rwb-secrets`; no secret value enters the environment.

- [ ] **Step 4: Run GREEN security and dependent tests**

```bash
python -m pytest \
  tests/research_web/test_credential_backend.py \
  tests/research_web/test_connection_center.py \
  tests/research_web/test_mcp_registry.py \
  tests/research_web/test_mcp_transport.py \
  tests/research_web/test_mcp_installation.py \
  tests/research_web/test_automation_channels.py \
  --confcutdir=tests/research_web
```

Expected: pass; existing injected fake keyrings remain supported.

- [ ] **Step 5: Commit secret boundary**

```bash
git add app/research_web/credential_backend.py \
  app/research_web/datahub/connections.py app/research_web/mcp_registry/credentials.py \
  app/research_web/mcp_runtime/credentials.py app/research_web/mcp_runtime/installation_store.py \
  app/research_web/automation/channels.py app/research_web/service.py \
  tests/research_web/test_credential_backend.py tests/research_web/test_connection_center.py \
  tests/research_web/test_mcp_registry.py tests/research_web/test_mcp_transport.py \
  tests/research_web/test_mcp_installation.py tests/research_web/test_automation_channels.py
git commit -m "feat: store docker credentials outside image state"
```

## Task 10: Complete Doctor, logs and persistence/switching contracts

**Files:**
- Modify: `research_workbench_entrypoint/docker_runtime.py`
- Modify: `research_workbench_entrypoint/bootstrap.py`
- Modify: `app/research_web/service_manager.py`
- Modify: `app/cli/main.py`
- Modify: Docker/runtime/CLI tests

- [ ] **Step 1: Write RED output and state-transition tests**

Assert the Native Doctor payload is unchanged except additive fields:

```python
assert report["schema_version"] == 1
assert report["runtime_mode"] == "native"
assert set(previous_report).issubset(report)
```

Docker Doctor must report allowlisted engine/Compose/container/image/ports/mounts/services/capabilities, use `applicable: false` for Native-only Python/CJPY checks, and never include paths, container Env, labels outside the allowlist, auth Cookie or secret content. `ok` ignores optional `unavailable_in_docker` host integrations but fails on engine/container/Web/DSH/data/ownership issues.

Add real temporary data fixture tests that switch Native→Docker→Native through fake owned controllers, read the same fixture after each switch, and confirm each controller ignores the other's state. Test bounded Native log reading, Docker `--tail` limits, explicit follow and unknown ownership refusal.

- [ ] **Step 2: Run RED focused tests**

```bash
python -m pytest tests/research_web/test_service_manager.py \
  tests/research_web/test_docker_runtime.py \
  tests/research_web/test_runtime_mode.py \
  tests/research_web/test_cli_lazy.py \
  --confcutdir=tests/research_web
```

Expected: additive mode/log/capability assertions fail.

- [ ] **Step 3: Implement truthful additive projections**

Keep `services.runtime` and `services.web` for both modes. Docker PID is `None`; container identity is represented by a safe state enum and digested ownership ID. Add `web logs` to both bootstrap and Click so Native and Docker help remain consistent. Native log reader validates exact known files and caps bytes/lines; Docker log controller passes `--tail` and optional `--follow` without inspect.

- [ ] **Step 4: Run GREEN tests**

```bash
python -m pytest tests/research_web/test_service_manager.py \
  tests/research_web/test_docker_runtime.py \
  tests/research_web/test_runtime_mode.py \
  tests/research_web/test_cli_lazy.py \
  --confcutdir=tests/research_web
```

Expected: pass.

- [ ] **Step 5: Commit diagnostics and switching**

```bash
git add research_workbench_entrypoint/docker_runtime.py \
  research_workbench_entrypoint/bootstrap.py app/research_web/service_manager.py \
  app/cli/main.py tests/research_web/test_service_manager.py \
  tests/research_web/test_docker_runtime.py tests/research_web/test_runtime_mode.py \
  tests/research_web/test_cli_lazy.py
git commit -m "feat: diagnose and switch web runtimes safely"
```

## Task 11: Add conditional multi-architecture Docker CI

**Files:**
- Create: `.github/workflows/research-web-docker.yml`
- Modify: `.github/workflows/research-web-bootstrap.yml`
- Modify: `tests/javascript/actions_quota_governance.test.mjs`
- Modify: `tests/javascript/docker_runtime_contract.test.mjs`
- Modify: `docs/actions-budget.md`

- [ ] **Step 1: Write RED workflow contracts**

Assert the Docker workflow has only relevant path triggers; permissions `contents: read`; concurrency with cancellation; explicit timeout; Buildx/QEMU; amd64 and arm64; config/build/up/health/restart/persistence/down; three-day artifacts; and no secrets. Assert ordinary docs/UI paths do not trigger it and existing Native macOS Bootstrap remains unchanged.

```javascript
assert.deepEqual(workflow.permissions, { contents: "read" });
assert.equal(workflow.concurrency["cancel-in-progress"], true);
assert.deepEqual(new Set(job.strategy.matrix.platform), new Set(["linux/amd64", "linux/arm64"]));
assert.equal(job["timeout-minutes"] <= 60, true);
```

- [ ] **Step 2: Run RED workflow tests**

```bash
node --test tests/javascript/actions_quota_governance.test.mjs \
  tests/javascript/docker_runtime_contract.test.mjs
```

Expected: workflow is missing.

- [ ] **Step 3: Implement conditional workflow and cost contract**

Create one `docker-runtime` job using standard Ubuntu runner. Matrix both architectures; QEMU only supports arm64 emulation. Use unique temporary host data/state/secret directories, build with no secret args, run Compose health, create a non-secret fixture, down/up and verify it, restart, collect safe Doctor/health, then down and verify ports. Logs upload only on failure after a secret-pattern scan; successful artifacts contain safe JSON/Compose summary only.

Path triggers include Docker packaging, runtime contract/router/supervisor, setup/launchers, Web lock/CJPY/DSH runtime resources, policy/workflow tests and the workflow itself. They exclude ordinary UI/docs. Update actions-budget to state that multi-arch Docker proves Linux image behavior, not Native hosts or Docker Desktop integrations.

- [ ] **Step 4: Run GREEN workflow/governance tests**

```bash
node --test tests/javascript/actions_quota_governance.test.mjs \
  tests/javascript/docker_runtime_contract.test.mjs \
  tests/javascript/verification_policy.test.mjs
node scripts/check_documentation_governance.mjs --project .
```

Expected: pass.

- [ ] **Step 5: Commit conditional CI**

```bash
git add .github/workflows/research-web-docker.yml \
  .github/workflows/research-web-bootstrap.yml \
  tests/javascript/actions_quota_governance.test.mjs \
  tests/javascript/docker_runtime_contract.test.mjs docs/actions-budget.md
git commit -m "ci: verify docker runtime conditionally"
```

## Task 12: Update current-product, architecture and installation documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/research-web-installation.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DEVELOPMENT_MAP.md`
- Modify: `docs/AGENT_WORKFLOW.md`
- Modify: `docs/architecture/research-web/README.md`
- Modify: `docs/architecture/research-web/01-system.md`
- Modify: `docs/architecture/research-web/02-research-runtime.md`
- Modify: `docs/architecture/research-web/03-data-files.md`
- Modify: `docs/architecture/research-web/05-security-validation.md`
- Modify: `docs/architecture/research-web/architecture-map.json`
- Modify: `docs/architecture/research-web/readme-review.json`
- Modify: deployment diagram source/artifact/receipt selected by the architecture map
- Create: `.ai/reports/2026-09-29-native-docker-dual-runtime.md`

- [ ] **Step 1: Write documentation contract assertions first**

Extend governance/architecture tests so source/runtime/Docker/CLI paths require the authoritative dual-runtime docs and deployment diagram. Add README receipt expectations for an updated README. Run them before editing docs:

```bash
node --test tests/javascript/documentation_governance.test.mjs \
  tests/javascript/research_web_architecture.test.mjs
```

Expected: fail because new source/packaging is absent from the map and current docs describe Native only.

- [ ] **Step 2: Update user and operator docs**

README quick start must show:

```bash
./setup-web.sh --runtime docker
./rwb web doctor
```

Immediately retain:

```bash
./setup-web.sh --runtime native
```

Document explicit prerequisites, no-argument Native compatibility, mode/status/use/`--stop-current`, shared/isolated directories, Docker credential boundary, host-integration limitations, logs, Doctor issue codes, upgrade, repair, stop and non-destructive uninstall. Windows `.cmd` equivalents must be present without claiming Windows was tested.

- [ ] **Step 3: Update architecture and governance artifacts**

The deployment graph must show one product/source/data model with Native two-process and Docker single-container branches. Architecture map lists all new production sources, tests, docs and diagram evidence. Task report includes an `architecture-review` marker with `structure: changed` and the exact deployment diagram ID. README review receipt is `updated` with a concrete summary/reason.

- [ ] **Step 4: Run GREEN documentation gates**

```bash
node scripts/check_documentation_governance.mjs --project .
node --test tests/javascript/documentation_governance.test.mjs \
  tests/javascript/research_web_architecture.test.mjs
/opt/homebrew/bin/python3.12 scripts/generate_py_file_index.py --check
node .agents/project-constraints.mjs --project . \
  --changed-file README.md \
  --changed-file docs/research-web-installation.md \
  --changed-file Dockerfile \
  --changed-file app/research_web/process_spec.py
```

Expected: zero violations and current map/index.

- [ ] **Step 5: Commit docs and architecture evidence**

```bash
git add README.md docs .ai/reports/2026-09-29-native-docker-dual-runtime.md
git commit -m "docs: explain native and docker web runtimes"
```

## Task 13: Execute the complete local verification closure

**Files:**
- Create: `.ai/reports/2026-09-29-native-docker-dual-runtime-plan.json`
- Create: `.ai/reports/2026-09-29-native-docker-dual-runtime-receipt.json`
- Modify: `.ai/reports/2026-09-29-native-docker-dual-runtime.md`

- [ ] **Step 1: Build the authoritative changed-file set**

```bash
git diff --name-only -z origin/master...HEAD > /tmp/rwb-dual-runtime-files.z
```

Convert the NUL-delimited paths to repeated `--changed-file` arguments without hand-picking or omitting generated/docs/test files, then save the planner JSON to the report path.

- [ ] **Step 2: Run L0→L4 exactly as planned**

Run every `receiptTemplate.requiredValidationIds` command in order. At minimum the expected closure includes:

```bash
node scripts/check_documentation_governance.mjs --project .
/opt/homebrew/bin/python3.12 scripts/generate_py_file_index.py --check
node --test tests/javascript/verification_policy.test.mjs \
  tests/javascript/verification_receipt.test.mjs \
  tests/javascript/incremental_validation_skill.test.mjs \
  tests/javascript/docker_runtime_contract.test.mjs
python -m pytest tests/research_web/test_runtime_contract.py \
  tests/research_web/test_runtime_mode.py \
  tests/research_web/test_docker_runtime.py \
  tests/research_web/test_container_supervisor.py \
  tests/research_web/test_service_manager.py \
  tests/research_web/test_runtime_launch.py \
  tests/research_web/test_setup_web.py \
  tests/research_web/test_cli_lazy.py \
  tests/research_web/test_credential_backend.py \
  --confcutdir=tests/research_web
node --test tests/javascript/research_web_architecture.test.mjs \
  tests/javascript/documentation_governance.test.mjs \
  tests/javascript/actions_quota_governance.test.mjs
```

Use the planner output rather than this minimum list if it selects more. Any failure triggers replanning with `--signal validation_failure`; unexpected behavior uses `--signal unexpected_behavior`.

- [ ] **Step 3: Run Native macOS lifecycle acceptance**

Only after explicit authorization to install locked dependencies in the isolated worktree:

```bash
./setup-web.sh --runtime native --no-start
./rwb web start --no-open
./rwb web status --json
./rwb web doctor --json
./rwb web restart --no-open
./rwb web logs --tail 100
./rwb web stop
```

Record real PID/port/health transitions and confirm the canonical data fixture remains. Do not touch an independently running main-worktree service.

- [ ] **Step 4: Run Docker macOS arm64 acceptance when Docker is authorized/available**

```bash
./setup-web.sh --runtime docker --no-start
./rwb runtime use docker
./rwb web start --no-open
./rwb web status --json
./rwb web doctor --json
./rwb web restart --no-open
./rwb web logs --tail 100
./rwb web stop
```

Then run Native→Docker→Native with `--stop-current`, verifying the same non-secret fixture after each start and independent runtime state. On the current host Docker is absent; without explicit installation authorization this step remains `not_run` and the full receipt remains blocked.

- [ ] **Step 5: Validate the receipt and record Harness outcome**

```bash
node scripts/validate_verification_receipt.mjs --project . \
  --plan .ai/reports/2026-09-29-native-docker-dual-runtime-plan.json \
  --receipt .ai/reports/2026-09-29-native-docker-dual-runtime-receipt.json
```

Expected: validator succeeds only after every required local item has real evidence; external gates stay `not_run`/blocked until actual CI.

## Task 14: Review, managed integration and authorized delivery

**Files:**
- No new product files; this task acts on the verified branch and delivery receipts.

- [ ] **Step 1: Run a code review against the approved design**

Review requirement-by-requirement: Native default compatibility, one source/lock, no business duplication, single-container loopback, data persistence, state isolation, switching, secret absence, Doctor/logs, policy routing, CI cost and docs. Fix findings with new RED→GREEN evidence and replan the changed set.

- [ ] **Step 2: Read current delivery/budget state before remote actions**

```bash
sed -n '1,260p' docs/actions-budget.md
git remote -v
gh repo view --json visibility,defaultBranchRef
```

Expected: remote/visibility/default branch are current and `public-standard`, or delivery stops before push/dispatch.

- [ ] **Step 3: Prepare and integration-verify with the managed delivery controller**

Use the project-installed iteration-delivery workflow with `--delivery-required`; verify the merged integration worktree with the same complete planner closure. A second prepare is forbidden while already prepared; stale remote state requires reintegration, never force-push.

- [ ] **Step 4: Publish only with explicit user authorization**

Push/PR/merge/workflow dispatch are external state changes. If authorization is absent, report the locally verified branch and leave external gates blocked. If authorized, publish through the managed controller, wait for Project Constraints, Research Web Checks, macOS Native Bootstrap and conditional Docker workflow, and record run URLs/conclusions.

- [ ] **Step 5: Cleanup and final Harness gate**

After successful integration and CI, clean only controller-owned clean worktrees/branches, preserve unrelated worktrees, record the real completed/passed outcome with measured duration, and run:

```bash
node /Users/leon/.agents/leon-engineering/runtime/harness-enforce.mjs \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id dual-runtime-architecture \
  --require-delivery
```

Expected: Harness passes only when local evidence, publication and required external gates are real. Windows Native/real-machine and untested Docker Desktop host integrations remain explicitly outside any completion claim.

## Plan self-review receipt

- Spec coverage: all 26 objective sections map to Tasks 1–14; Docker MVP, runtime abstraction, CLI, setup, persistence/switching, verification/CI and docs have independent RED→GREEN checkpoints.
- Dependency consistency: runtime-mode store precedes controller/bootstrap; process-state separation precedes supervisor; supervisor precedes packaging; controller precedes setup; packaging/runtime precede Docker CI and docs.
- Safety: no task installs Docker, Python packages, pushes, dispatches, deletes data or publishes without the separately required authorization.
- Backward compatibility: missing mode remains Native; no-argument setup remains Native; existing Native manager owns unchanged PID semantics; Docker never substitutes for Native platform evidence.
- Placeholder scan: the plan contains no deferred markers; every interface is paired with explicit behavior, tests and failure handling.
