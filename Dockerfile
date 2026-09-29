# syntax=docker/dockerfile:1
ARG NODE_IMAGE=node:24.19.0-bookworm-slim
ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm
FROM ${NODE_IMAGE} AS node-runtime

FROM ${PYTHON_IMAGE} AS python-builder
WORKDIR /opt/rwb
ENV VIRTUAL_ENV=/opt/rwb/venv \
    PATH=/opt/rwb/venv/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements/web.lock requirements/web.lock
RUN python -m venv /opt/rwb/venv \
    && python -m pip install --require-hashes -r requirements/web.lock \
    && python -m pip check
COPY pyproject.toml ./
COPY app/__init__.py app/__init__.py
COPY app/research_web app/research_web
COPY app/cli app/cli
COPY core/__init__.py core/__init__.py
COPY core/settings core/settings
COPY core/observability core/observability
COPY research_workbench_entrypoint research_workbench_entrypoint
COPY runtimes/__init__.py runtimes/research_web.json runtimes/
COPY vendor/cjpy vendor/cjpy
COPY vendor/dsh-tabbit vendor/dsh-tabbit
COPY scripts/setup_web.py scripts/setup_web.py
COPY docker docker
RUN python -c 'from pathlib import Path; from scripts.setup_web import SetupWebInstaller; SetupWebInstaller(project_root=Path.cwd(), data_home=Path("/tmp/rwb-build")).verify_cjpy_bundle()' \
    && python -m pip install --no-build-isolation --no-deps . \
    && python -m pip install --no-index --no-deps vendor/cjpy/0.5.2/cjpy-0.5.2-py3-none-any.whl

FROM python-builder AS dsh-builder
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates g++ make \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install --global corepack@0.34.0 \
    && corepack enable
RUN python - <<'PY'
import logging
import subprocess
from pathlib import Path
from scripts.setup_web import SetupWebInstaller, DSH_REMOTE, DSH_COMMIT

logging.basicConfig(level=logging.INFO)
source = Path('/opt/rwb/dsh')
source.mkdir()
for args in (
    ['git', 'init', str(source)],
    ['git', '-C', str(source), 'remote', 'add', 'origin', DSH_REMOTE],
    ['git', '-C', str(source), 'fetch', '--depth=1', 'origin', DSH_COMMIT],
    ['git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD'],
):
    subprocess.run(args, check=True, timeout=600)
SetupWebInstaller(project_root=Path.cwd(), data_home=Path('/tmp/rwb-build')).verify_dsh_source(source, require_build=False)
logging.info('docker_dsh_source_verified')
PY
WORKDIR /opt/rwb/dsh
RUN corepack pnpm@11.7.0 install --frozen-lockfile \
    && corepack pnpm@11.7.0 run build
WORKDIR /opt/rwb
RUN python - <<'PY'
import logging
import shutil
import subprocess
from pathlib import Path
from scripts.setup_web import SetupWebInstaller, DSH_COMMIT

logging.basicConfig(level=logging.INFO)
source = Path('/opt/rwb/dsh')
installer = SetupWebInstaller(project_root=Path.cwd(), data_home=Path('/tmp/rwb-build'))
verified = installer.verify_dsh_source(source)
# The launcher checks git rev-parse HEAD. Retain only this verified public identity,
# not checkout history, remote configuration, credentials, hooks, or Git objects.
shutil.rmtree(source / '.git')
for name in ('objects', 'refs'):
    (source / '.git' / name).mkdir(parents=True)
(source / '.git' / 'HEAD').write_text(DSH_COMMIT + '\n')
assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == DSH_COMMIT
assert installer.calculate_dsh_closure(source) == (verified['closure_sha256'], verified['closure_files'])
logging.info('docker_dsh_closure_verified files=%s', verified['closure_files'])
PY

FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates libstdc++6 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 rwb \
    && useradd --uid 10001 --gid 10001 --create-home rwb \
    && install -d -m 700 -o rwb -g rwb /data/research-web /state /run/rwb-secrets
WORKDIR /opt/rwb
ENV VIRTUAL_ENV=/opt/rwb/venv \
    PATH=/opt/rwb/venv/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RWB_DATA_ROOT=/data/research-web \
    RWB_RUNTIME_STATE=/state \
    LOG_DIR=/state/logs \
    OBJECT_STORAGE_PATH=/data/research-web/objects \
    PDF_MARKDOWN_DIR=/data/research-web/markdown \
    PDF_RAW_TEXT_DIR=/data/research-web/raw_text \
    RESEARCH_RUN_MODE=web-prod
LABEL io.research-workbench.runtime="docker"
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=dsh-builder /usr/local/lib/node_modules/corepack /usr/local/lib/node_modules/corepack
COPY --from=python-builder /opt/rwb/venv /opt/rwb/venv
COPY --from=python-builder /opt/rwb/app /opt/rwb/app
COPY --from=python-builder /opt/rwb/core /opt/rwb/core
COPY --from=python-builder /opt/rwb/research_workbench_entrypoint /opt/rwb/research_workbench_entrypoint
COPY --from=python-builder /opt/rwb/runtimes /opt/rwb/runtimes
COPY --from=python-builder /opt/rwb/vendor/dsh-tabbit /opt/rwb/vendor/dsh-tabbit
COPY --from=python-builder --chmod=755 /opt/rwb/docker /opt/rwb/docker
COPY --from=python-builder /opt/rwb/pyproject.toml /opt/rwb/pyproject.toml
COPY outputs/research-web-architecture /opt/rwb/outputs/research-web-architecture
COPY --from=dsh-builder --chown=rwb:rwb /opt/rwb/dsh /opt/dsh
RUN ln -s /usr/local/lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
USER rwb
VOLUME ["/data/research-web", "/state", "/run/rwb-secrets"]
EXPOSE 8088
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=3 CMD ["/opt/rwb/venv/bin/python", "/opt/rwb/docker/healthcheck.py"]
ENTRYPOINT ["/opt/rwb/docker/entrypoint.sh"]
