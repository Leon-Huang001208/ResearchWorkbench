# Host Capacity Resource Monitor Report

**Date:** 2026-08-05
**Task:** Add host CPU and memory capacity to controlled resource snapshots
**Status:** Complete

## Scope

- Added host CPU, logical-core and virtual-memory fields to `ResourceMonitoringService` snapshots.
- Added application-to-host CPU and memory percentages to the existing summary.
- Preserved the controlled PID collection boundary: no system-process enumeration was added.

## Failure Handling

- The first non-blocking host CPU sample is treated as a warm-up baseline and remains unknown.
- Invalid values and psutil failures return `None`, emit a `host_field_unavailable` warning, and log a structured `error_type`.

## Verification

| Command | Result |
| --- | --- |
| `python -m pytest tests/unit/test_resource_monitor_service.py -q` | 20 passed |
| `ruff check services/resource_monitor_service.py tests/unit/test_resource_monitor_service.py` | passed |
| `black --check services/resource_monitor_service.py tests/unit/test_resource_monitor_service.py` | passed |
| `isort --check-only services/resource_monitor_service.py tests/unit/test_resource_monitor_service.py` | passed |

## Risk

The validation only covers the service unit suite on the local host. It does not establish platform-specific behavior beyond psutil's mocked failure paths.
