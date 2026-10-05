#!/bin/sh
set -eu
: "${RWB_DATA_ROOT:=/data/research-web}"
: "${RWB_RUNTIME_STATE:=/state/runtime}"
: "${RESEARCH_CREDENTIAL_HOME:=/run/rwb-secrets/private}"
test -d "$RWB_DATA_ROOT" && test -w "$RWB_DATA_ROOT"
test -d "${RWB_RUNTIME_STATE%/*}" && test -w "${RWB_RUNTIME_STATE%/*}"
test -d "${RESEARCH_CREDENTIAL_HOME%/*}" && test -w "${RESEARCH_CREDENTIAL_HOME%/*}"
export RWB_DATA_ROOT RWB_RUNTIME_STATE RESEARCH_CREDENTIAL_HOME
exec /opt/rwb/venv/bin/python /opt/rwb/docker/supervisor.py
