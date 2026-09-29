#!/bin/sh
set -eu
: "${RWB_DATA_ROOT:=/data/research-web}"
: "${RWB_RUNTIME_STATE:=/state}"
test -d "$RWB_DATA_ROOT" && test -w "$RWB_DATA_ROOT"
test -d "$RWB_RUNTIME_STATE" && test -w "$RWB_RUNTIME_STATE"
exec /opt/rwb/venv/bin/python /opt/rwb/docker/supervisor.py
