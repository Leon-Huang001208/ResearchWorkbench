"""Admin-only local fault driver. Never copied into an application image.

Only the fixed g2b-rehearsal target is used; its trusted purpose must be rehearsal.
The controller is loaded from an immutable release and validates its own seal.
The historical r0d/r1a chain is intentionally explicit in these reproductions.
"""

import importlib.util
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/ledger/releases/r1a/control")
spec = importlib.util.spec_from_file_location(
    "frozen_release", "/ledger/releases/r1a/control/release.py"
)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
logging.basicConfig(filename="/ledger/logs/g2b/fault-controller.log", level=logging.INFO)
s = r.ReleaseStore(Path("/ledger"), os.environ["RWB_MANAGER_ROOT"], os.environ["RWB_WORKTREE"])
mode = sys.argv[1]
try:
    if mode == "candidate-failure":
        plan = s.plan("r1a", "prod", "g2b-rehearsal")
        original = s.probe
        injected = False

        def fail_candidate(record, artifact):
            global injected
            if artifact["release_id"] == "r1a" and not injected:
                injected = True
                owned = s.manager.owned(record)
                assert owned["State"]["Running"]
                r.manage.command("docker", "kill", "--signal=TERM", record["container_id"])
                print(
                    json.dumps({"injected": "owned_candidate_term", "id": record["container_id"]}),
                    flush=True,
                )
            return original(record, artifact)

        s.probe = fail_candidate
        try:
            s.apply("r1a", plan)
        except r.Refusal as exc:
            assert str(exc) == "candidate_failed_previous_restored", str(exc)
            state = s.manager.read("prod", "g2b-rehearsal")
            assert injected and state["accepted_release"] == "r0d"
            assert state["deployment"]["state"] == "restored"
            print(
                json.dumps(
                    {
                        "candidate_failed": True,
                        "old_restored": True,
                        "accepted": state["accepted_release"],
                    }
                )
            )
        else:
            raise AssertionError("bad_candidate_was_accepted")
    elif mode == "interrupt":
        plan = s.plan("r1a", "prod", "g2b-rehearsal")
        original = s.control

        def interrupted(record, action, transaction):
            result = original(record, action, transaction)
            if action == "begin":
                r.manage.atomic_json(
                    Path("/ledger/logs/g2b/interruption-ready.json"),
                    {
                        "transaction": transaction,
                        "maintenance": True,
                        "container_id": record["container_id"],
                    },
                )
                print("maintenance_begin_acknowledged", flush=True)
                while True:
                    time.sleep(1)
            return result

        s.control = interrupted
        s.apply("r1a", plan)
    elif mode == "refusals":
        before = s.manager.read("prod", "g2b-rehearsal")
        plan = s.plan("r1a", "prod", "g2b-rehearsal")
        results = {}
        for name, changes, expected in (
            ("expired_plan", {"expires_at": 0}, "plan_expired"),
            (
                "wrong_image",
                {"local_image_id": "sha256:" + "0" * 64},
                "plan_release_identity_mismatch",
            ),
            (
                "wrong_seal",
                {"release_seal": "sha256:" + "0" * 64},
                "plan_release_identity_mismatch",
            ),
            ("stale_plan", {"target_hash": "sha256:" + "0" * 64}, "stale_plan"),
        ):
            try:
                s.apply("r1a", {**plan, **changes})
            except r.Refusal as exc:
                assert str(exc) == expected, str(exc)
                results[name] = True
            else:
                raise AssertionError(name)
            assert s.manager.read("prod", "g2b-rehearsal") == before
        print(json.dumps({"refusals": results, "target_unchanged": True}))
    else:
        raise ValueError("fixture_mode_unknown")
except Exception as exc:
    logging.error("fixture_failed category=%s", type(exc).__name__)
    raise
