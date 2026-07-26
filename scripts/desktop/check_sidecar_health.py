"""Start one desktop sidecar, wait for its local health endpoint, then stop it."""

from __future__ import annotations

import argparse
import errno
import logging
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_FILE = REPO_ROOT / "build" / "desktop-sidecar" / "health-smoke.log"
HEALTH_HOST = "127.0.0.1"
POLL_INTERVAL_SECONDS = 0.25
CHILD_STOP_TIMEOUT_SECONDS = 5
PORT_RELEASE_TIMEOUT_SECONDS = 5
# Sidecar health checks always target the local loopback interface.  Do not
# inherit a developer's HTTP proxy here, otherwise a stale proxy can make a
# healthy local sidecar appear unavailable.
LOCAL_HTTP_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def is_windows() -> bool:
    """Return whether this helper is running on Windows."""
    return os.name == "nt"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the isolated sidecar health check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, help="Path to the native sidecar executable")
    parser.add_argument("--port", required=True, type=int, help="Unused local port for the sidecar")
    parser.add_argument(
        "--timeout-seconds",
        required=True,
        type=float,
        help="Maximum time to wait for GET /health to return HTTP 200",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help=f"Combined sidecar and health-check log (default: {DEFAULT_LOG_FILE})",
    )
    return parser


def configure_logger(log_file: Path) -> tuple[logging.Logger, logging.Handler]:
    """Create a dedicated file logger without changing global logging configuration."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("alphafoundry.desktop.sidecar_health")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger, handler


def sidecar_command(executable: str, port: int) -> list[str]:
    """Return the exact command used to start the sidecar under test."""
    return [executable, "--host", HEALTH_HOST, "--port", str(port)]


def endpoint_is_healthy(port: int) -> bool:
    """Return whether the local endpoint currently answers a successful health request."""
    endpoint = f"http://{HEALTH_HOST}:{port}/health"
    with LOCAL_HTTP_OPENER.open(endpoint, timeout=POLL_INTERVAL_SECONDS) as response:
        return response.status == 200


def wait_for_health(port: int, timeout_seconds: float, logger: logging.Logger) -> bool:
    """Poll the local sidecar health endpoint until it is ready or the deadline expires."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            if endpoint_is_healthy(port):
                logger.info("Sidecar health endpoint returned HTTP 200")
                return True
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            logger.info("Sidecar health endpoint is not ready: %s", error)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.error("Sidecar did not become healthy within %.2f seconds", timeout_seconds)
            return False
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))


def wait_for_port_release(port: int, logger: logging.Logger) -> bool:
    """Confirm that the sidecar port is no longer accepting local connections."""
    deadline = time.monotonic() + PORT_RELEASE_TIMEOUT_SECONDS
    while True:
        try:
            with socket.create_connection((HEALTH_HOST, port), timeout=POLL_INTERVAL_SECONDS):
                logger.info("Waiting for helper-owned sidecar port %s to close", port)
        except OSError as error:
            if isinstance(error, ConnectionRefusedError) or error.errno == errno.ECONNREFUSED:
                logger.info("Helper-owned sidecar port %s is released", port)
                return True
            # After taskkill on Windows, a released loopback listener can report
            # WSAETIMEDOUT instead of ECONNREFUSED. The helper already waited for
            # its own child tree, so no successful connection means that child is
            # no longer accepting requests.
            if is_windows() and isinstance(error, TimeoutError):
                logger.info("Helper-owned Windows sidecar port %s is no longer accepting", port)
                return True
            logger.info("Port %s has not conclusively closed yet: %s", port, error)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.error("Helper-owned sidecar port %s remained open after cleanup", port)
            return False
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))


def stop_posix_process_group(
    process: subprocess.Popen[bytes],
    port: int,
    logger: logging.Logger,
    process_group: int | None = None,
) -> bool:
    """Terminate and, if required, kill only the helper-created POSIX process group."""
    try:
        process_group = process_group if process_group is not None else os.getpgid(process.pid)
        os.killpg(process_group, signal.SIGTERM)
        try:
            process.wait(timeout=CHILD_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            logger.warning("Sidecar group ignored TERM; killing only the helper-owned process group")
            os.killpg(process_group, signal.SIGKILL)
            process.wait(timeout=CHILD_STOP_TIMEOUT_SECONDS)
        if wait_for_port_release(port, logger):
            return True
        logger.warning("Sidecar port remained open after TERM; killing helper-owned process group")
        os.killpg(process_group, signal.SIGKILL)
        process.wait(timeout=CHILD_STOP_TIMEOUT_SECONDS)
        return wait_for_port_release(port, logger)
    except (ProcessLookupError, PermissionError):
        logger.info("Helper-owned sidecar process group already exited or is inaccessible")
        return wait_for_port_release(port, logger)
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Unable to stop helper-owned sidecar process group")
        return False


def stop_windows_process_tree(
    process: subprocess.Popen[bytes], port: int, logger: logging.Logger
) -> bool:
    """Use taskkill to stop only the helper-owned Windows parent PID and its tree."""
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0 and process.poll() is None:
            logger.error("taskkill failed for helper-owned sidecar PID %s", process.pid)
            return False
        process.wait(timeout=CHILD_STOP_TIMEOUT_SECONDS)
        return wait_for_port_release(port, logger)
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Unable to stop helper-owned Windows sidecar process tree")
        return False


def stop_child(
    process: subprocess.Popen[bytes],
    port: int,
    logger: logging.Logger,
    process_group: int | None = None,
) -> bool:
    """Stop only this helper's sidecar and confirm its listening port was released."""
    if is_windows():
        return stop_windows_process_tree(process, port, logger)
    return stop_posix_process_group(process, port, logger, process_group)


def run_health_check(
    executable: str,
    port: int,
    timeout_seconds: float,
    log_file: Path = DEFAULT_LOG_FILE,
) -> int:
    """Run the health check and return zero only after the sidecar becomes healthy."""
    logger, handler = configure_logger(log_file)
    process: subprocess.Popen[bytes] | None = None
    process_group: int | None = None
    log_stream = None
    result = 1
    cleanup_succeeded = True
    try:
        if port < 1 or port > 65535:
            logger.error("Port must be in the range 1-65535: %s", port)
        elif timeout_seconds <= 0:
            logger.error("Timeout must be positive: %s", timeout_seconds)
        else:
            log_stream = log_file.open("ab")
            command = sidecar_command(executable, port)
            logger.info("Starting helper-owned sidecar: %s", command)
            popen_kwargs: dict[str, object] = {
                "stdout": log_stream,
                "stderr": subprocess.STDOUT,
                "env": os.environ.copy(),
            }
            if not is_windows():
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **popen_kwargs)
            if not is_windows():
                process_group = os.getpgid(process.pid)
            result = 0 if wait_for_health(port, timeout_seconds, logger) else 1
    except OSError:
        logger.exception("Unable to start or inspect helper-owned sidecar")
    finally:
        if process is not None:
            cleanup_succeeded = stop_child(process, port, logger, process_group)
        if log_stream is not None:
            log_stream.close()
        logger.removeHandler(handler)
        handler.close()
    if not cleanup_succeeded:
        return 1
    return result


def main(argv: Sequence[str] | None = None) -> None:
    """Run the CLI and terminate with the health-check result code."""
    args = build_parser().parse_args(argv)
    raise SystemExit(
        run_health_check(
            executable=args.executable,
            port=args.port,
            timeout_seconds=args.timeout_seconds,
            log_file=args.log_file,
        )
    )


if __name__ == "__main__":
    main()
