"""Iteration closeout must be bounded, recoverable and task-specific."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from research_workbench_entrypoint import iteration_resources as resources
from research_workbench_entrypoint.iteration_cache import ManagedCaches
from research_workbench_entrypoint.iteration_resources import (
    GIB,
    ResourceError,
    cache_budget,
    clean_dependencies,
    occupied,
    preserve_evidence,
    record_task,
    register_directory,
    task_resource_plan,
)
from scripts.test_artifact_retention import create_root, retire_root


def passed_bundle(root: Path, logs: Path, *, exact_checkout: bool = True) -> dict:
    logs.mkdir()
    lease = logs / "batch-lease.json"
    with patch(
        "scripts.test_artifact_retention._checkout_identity", return_value=root
    ):
        create_root(
            root / "pytest-temp",
            lease,
            task_id="retention-test",
            candidate="a" * 40,
            batch_id="batch-01",
            node_ids=["tests/research_web/test_fixture.py::test_pass"],
            _exact_checkout=exact_checkout,
        )
    owner = json.loads(lease.read_text())
    junit = logs / "passed.xml"
    junit.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0">'
        '<testcase name="test_pass"/></testsuite></testsuites>'
    )
    raw = logs / "raw.log"
    raw.write_text("reproducible local pass output")
    stderr = logs / "stderr.log"
    stderr.write_text("")
    result = logs / "batch-result.json"
    result.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "taskId": "retention-test",
                "candidate": "a" * 40,
                "rootNonce": owner["nonce"],
                "batchId": "batch-01",
                "nodeIds": ["tests/research_web/test_fixture.py::test_pass"],
                "exitCode": 0,
                "junitSha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
                "stdoutSha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "stderrSha256": hashlib.sha256(stderr.read_bytes()).hexdigest(),
            }
        )
    )
    with patch("scripts.test_artifact_retention._checkout_identity", return_value=root):
        retire_root(lease, junit, raw, stderr, result, open_files=lambda _path: False)
    return {"lease": lease, "junit": junit, "raw": raw, "stderr": stderr, "result": result}


def discard_row(bundle: dict, path: Path) -> dict:
    return {
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "proof": bundle["junit"].name,
        "proofSha256": hashlib.sha256(bundle["junit"].read_bytes()).hexdigest(),
        "batchReceipt": bundle["lease"].name,
        "batchReceiptSha256": hashlib.sha256(bundle["lease"].read_bytes()).hexdigest(),
    }


class CacheDriver:
    def __init__(self, used, active=()):
        self.used = dict(used)
        self.active = set(active)
        self.calls = []

    def cache_usage(self, builder):
        return {"bytes": self.used[builder], "oldestSeconds": 100 if builder == "a" else 50}

    def cache_prune(self, builder, target):
        self.calls.append((builder, target))
        if builder not in self.active:
            self.used[builder] = target


class IterationResourceTests(unittest.TestCase):
    def test_new_task_requires_selective_evidence_while_legacy_record_keeps_its_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "state"
            state.mkdir()
            with patch(
                "research_workbench_entrypoint.iteration_resources.state_paths",
                return_value=(root, state, {}),
            ):
                record_task(root, "retention-test")
                first = json.loads((state / "resources.json").read_text())
                self.assertEqual(first["evidencePolicy"], "selective-v1")
                (state / "resources.json").write_text(
                    json.dumps({"taskId": "retention-test", "roots": {}, "directories": []})
                )
                record_task(root, "retention-test")
                legacy = json.loads((state / "resources.json").read_text())
                self.assertNotIn("evidencePolicy", legacy)

    def test_controller_argv_is_exempt_but_other_process_and_cwd_remain_protected(self):
        clear=SimpleNamespace(returncode=1,stderr='',stdout='')
        own=SimpleNamespace(stdout='100 99 python -m controller\n99 1 node /task/scripts/git_safety.mjs\n1 0 init\n')
        other=SimpleNamespace(stdout=own.stdout+'200 1 node /task/service.mjs\n')
        with patch('research_workbench_entrypoint.iteration_resources.os.getpid',return_value=100):
            with patch('research_workbench_entrypoint.iteration_resources.subprocess.run',side_effect=[clear,own]):self.assertFalse(occupied(Path('/task')))
            with patch('research_workbench_entrypoint.iteration_resources.subprocess.run',side_effect=[clear,other]):self.assertTrue(occupied(Path('/task')))
            with patch('research_workbench_entrypoint.iteration_resources.subprocess.run',return_value=SimpleNamespace(returncode=0)):
                self.assertTrue(occupied(Path('/task')))

    def test_only_registered_empty_generated_directories_use_rmdir(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();empty=root/'data/markdown';empty.mkdir(parents=True)
            record=register_directory(root,empty,'empty-directory')
            (empty/'business.md').write_text('must keep')
            result=clean_dependencies([record],occupied=lambda _:False,tracked=lambda _:False)
            self.assertFalse(result['ok']);self.assertEqual((empty/'business.md').read_text(),'must keep')
            (empty/'business.md').unlink()
            self.assertTrue(clean_dependencies([record],occupied=lambda _:False,tracked=lambda _:False)['ok'])
            self.assertFalse(empty.exists())

    def test_other_task_unknown_and_rollback_images_are_protected(self):
        def row(identity, task, project=True):
            labels={'io.research-workbench.delivery-task':task,'io.research-workbench.lifetime':'temporary','io.research-workbench.completed':'true'}
            if project:labels['io.research-workbench.project']='research-workbench'
            return {'id':identity,'tags':[identity], 'labels':labels}
        inventory={'containers':[],'images':[row('own','current'),row('other','other'),row('unknown','current',False),row('rollback','current')],'volumes':[]}
        plan=task_resource_plan(inventory,{'images':['rollback'],'installations':[]},'current')
        actions={v['id']:v['action'] for v in plan['resources']}
        self.assertEqual(actions,{'own':'delete','other':'keep','unknown':'keep','rollback':'keep'})

    def test_session_records_explicit_delivery_without_changing_session_identity(self):
        from research_workbench_entrypoint.docker_resources import ResourceSession
        session=ResourceSession(None,'fixture',delivery_task='current')
        self.assertEqual(session.labels['io.research-workbench.delivery-task'],'current')
        self.assertNotEqual(session.labels['io.research-workbench.task'],'current')

    def test_maintenance_restores_stopped_builder_limits_even_when_gc_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();(root/'builder.id').write_text('identity-proof')
            original={'Id':'builder-id','Image':'sha256:original','State':{'Running':False},'Mounts':[{'Type':'volume','Name':'rwb-dev-builder-state'}],'HostConfig':{'Memory':5*GIB,'MemorySwap':5*GIB}}
            class Fake(ManagedCaches):
                def __init__(self):super().__init__(root);self.current=copy.deepcopy(original);self.calls=[]
                def builder_binding(self,builder):return ('bound',)
                def inspect(self,name):return copy.deepcopy(self.current)
                def cache_usage(self,builder):return {'inUse':0}
                def call(self,*args,**kwargs):
                    self.calls.append(args)
                    if args[:2]==('context','show'):return 'desktop-linux'
                    if args[0]=='inspect':return 'identity-proof'
                    if args[:2]==('volume','inspect'):return json.dumps({'io.research-workbench.manager':str(root)})
                    if args[0]=='ps':return ''
                    if args[0]=='info':return str(8*GIB)
                    if args[0]=='update':self.current['HostConfig'].update(Memory=int(args[2]),MemorySwap=int(args[4]))
                    if args[0]=='start':self.current['State']['Running']=True
                    if args[0]=='stop':self.current['State']['Running']=False
                    return ''
            driver=Fake()
            with self.assertRaisesRegex(ResourceError,'fixture_gc_failure'), driver.maintenance():
                self.assertEqual(driver.current['HostConfig']['Memory'],2*GIB)
                raise ResourceError('fixture_gc_failure')
            self.assertEqual(driver.current,original)
            self.assertFalse((root/'operation.lock').exists())

    def test_existing_builder_operation_lock_is_never_removed(self):
        from research_workbench_entrypoint.iteration_cache import operation_lock
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();lock=root/'operation.lock';lock.mkdir();(lock/'proof').write_text('active build')
            with self.assertRaises(ResourceError), operation_lock(root):
                self.fail('must refuse concurrent maintenance')
            self.assertEqual((lock/'proof').read_text(),'active build')

    def test_rebound_builder_is_rejected_even_if_old_container_exists(self):
        driver = ManagedCaches(Path('/unused'))
        values = ['Name: rwb-dev-builder\nDriver: docker-container\nName: other-node\nEndpoint: ssh://remote\n', json.dumps('unix://' + str(Path.home()/'.docker/run/docker.sock'))]
        with patch.object(driver, 'call', side_effect=values), self.assertRaises(ResourceError):
            driver.builder_binding('rwb-dev-builder')

    def test_archive_keeps_original_on_copy_failure_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root/'logs'
            logs.mkdir()
            (logs/'report.md').write_text('proof')
            record = register_directory(root, logs, 'evidence')
            with patch('research_workbench_entrypoint.iteration_resources.occupied', return_value=False):
                def partial_copy(source, destination, **kwargs):
                    destination.write(b'partial-proof')
                    raise OSError('fixture disk full after partial write')
                with patch('research_workbench_entrypoint.iteration_resources.shutil.copyfileobj', side_effect=partial_copy), self.assertRaises(OSError):
                    preserve_evidence([record], root/'archive')
                self.assertTrue((logs/'report.md').exists())
                result = preserve_evidence([record], root/'archive')
                self.assertEqual(result[0]['status'], 'preserved')
                self.assertFalse(logs.exists())
                self.assertEqual(preserve_evidence([record], root/'archive')[0]['status'], 'already_preserved')

    def test_evidence_archive_tamper_blocks_source_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); logs=root/'logs'; logs.mkdir(); (logs/'proof').write_text('original')
            record=register_directory(root,logs,'evidence')
            with patch('research_workbench_entrypoint.iteration_resources.occupied',return_value=False), patch('research_workbench_entrypoint.iteration_resources.shutil.copyfileobj',side_effect=OSError('fixture')), self.assertRaises(OSError):
                preserve_evidence([record],root/'archive')
            target=next((root/'archive').iterdir())/'logs/proof';target.write_text('changed')
            with patch('research_workbench_entrypoint.iteration_resources.occupied',return_value=False), self.assertRaises(ResourceError):
                preserve_evidence([record],root/'archive')
            self.assertEqual((logs/'proof').read_text(),'original')

    def test_selected_evidence_discards_only_passed_raw_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root / "logs"
            bundle = passed_bundle(root, logs)
            (logs / "final.json").write_text('{"status":"PASS"}')
            selection = {
                "schemaVersion": 1,
                "keep": sorted(path.name for path in logs.iterdir() if path.name != "raw.log"),
                "discard": [discard_row(bundle, bundle["raw"])],
            }
            (logs / "evidence-retention.json").write_text(json.dumps(selection))
            record = register_directory(root, logs, "evidence")
            with patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ):
                result = preserve_evidence(
                    [record], root / "archive", policy="selective-v1", task_id="retention-test"
                )
            archive = next((root / "archive").iterdir()) / "logs"
            self.assertEqual(result[0]["discardedFiles"], 1)
            self.assertFalse(logs.exists())
            self.assertTrue((archive / "final.json").exists())
            self.assertTrue((archive / "passed.xml").exists())
            self.assertTrue((archive / "batch-lease.json").exists())
            self.assertTrue((archive / "evidence-retention.json").exists())
            self.assertFalse((archive / "raw.log").exists())
            self.assertEqual(
                preserve_evidence(
                    [record], root / "archive", policy="selective-v1", task_id="retention-test"
                )[0]["status"],
                "already_preserved",
            )
            lease_path = archive / "batch-lease.json"
            lease = json.loads(lease_path.read_text())
            lease["status"] = "active"
            lease_path.write_text(json.dumps(lease))
            selection_path = archive / "evidence-retention.json"
            selection = json.loads(selection_path.read_text())
            selection["discard"][0]["batchReceiptSha256"] = hashlib.sha256(
                lease_path.read_bytes()
            ).hexdigest()
            selection_path.write_text(json.dumps(selection))
            manifest_path = archive.parent / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["batch-lease.json"] = hashlib.sha256(lease_path.read_bytes()).hexdigest()
            manifest["evidence-retention.json"] = hashlib.sha256(
                selection_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ResourceError):
                preserve_evidence(
                    [record], root / "archive", policy="selective-v1", task_id="retention-test"
                )

    def test_selected_evidence_cannot_discard_final_receipt_using_passed_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root / "logs"
            bundle = passed_bundle(root, logs)
            final = logs / "final.json"
            final.write_text('{"status":"PASS","candidate":"final"}')
            (logs / "evidence-retention.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "keep": sorted(
                            path.name for path in logs.iterdir() if path.name != "final.json"
                        ),
                        "discard": [discard_row(bundle, final)],
                    }
                )
            )
            record = register_directory(root, logs, "evidence")
            with patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaisesRegex(ResourceError, "closeout_evidence_not_batch_output"):
                preserve_evidence(
                    [record], root / "archive", policy="selective-v1", task_id="retention-test"
                )
            self.assertTrue(final.exists())

    def test_wip_batch_cannot_authorize_automatic_log_discard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root / "logs"
            bundle = passed_bundle(root, logs, exact_checkout=False)
            (logs / "evidence-retention.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "keep": sorted(
                            path.name for path in logs.iterdir() if path.name != "raw.log"
                        ),
                        "discard": [discard_row(bundle, bundle["raw"])],
                    }
                )
            )
            record = register_directory(root, logs, "evidence")
            with patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaisesRegex(ResourceError, "closeout_evidence_batch_unverified"):
                preserve_evidence(
                    [record], root / "archive", policy="selective-v1", task_id="retention-test"
                )
            self.assertTrue(bundle["raw"].exists())

    def test_selected_evidence_rejects_unlisted_file_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root / "logs"
            logs.mkdir()
            (logs / "final.json").write_text("proof")
            (logs / "unlisted.raw").write_text("must not disappear")
            (logs / "evidence-retention.json").write_text(
                json.dumps({"schemaVersion": 1, "keep": ["final.json"], "discard": []})
            )
            record = register_directory(root, logs, "evidence")
            with patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaises(ResourceError):
                preserve_evidence([record], root / "archive", policy="selective-v1")
            self.assertEqual((logs / "unlisted.raw").read_text(), "must not disappear")

    def test_selected_evidence_rejects_failed_junit_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root / "logs"
            bundle = passed_bundle(root, logs)
            junit = bundle["junit"]
            junit.write_text(
                '<testsuites><testsuite tests="1" failures="0" errors="0">'
                '<testcase name="test_failed"><failure>real failure</failure></testcase>'
                '</testsuite></testsuites>'
            )
            raw = bundle["raw"]
            (logs / "evidence-retention.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "keep": sorted(
                            path.name for path in logs.iterdir() if path.name != "raw.log"
                        ),
                        "discard": [discard_row(bundle, raw)],
                    }
                )
            )
            record = register_directory(root, logs, "evidence")
            with patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaisesRegex(ResourceError, "closeout_evidence_proof_not_passed"):
                preserve_evidence(
                    [record], root / "archive", policy="selective-v1", task_id="retention-test"
                )
            self.assertEqual(raw.read_text(), "reproducible local pass output")

    def test_new_evidence_policy_requires_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root / "logs"
            logs.mkdir()
            (logs / "proof").write_text("keep")
            record = register_directory(root, logs, "evidence")
            with patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaises(ResourceError):
                preserve_evidence([record], root / "archive", policy="selective-v1")
            self.assertTrue((logs / "proof").exists())

    def test_selected_evidence_budget_blocks_oversized_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            logs = root / "logs"
            logs.mkdir()
            (logs / "proof").write_text("keep")
            (logs / "evidence-retention.json").write_text(
                json.dumps({"schemaVersion": 1, "keep": ["proof"], "discard": []})
            )
            record = register_directory(root, logs, "evidence")
            with patch(
                "research_workbench_entrypoint.iteration_resources.EVIDENCE_ARCHIVE_MAX_BYTES",
                1,
            ), patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaisesRegex(ResourceError, "closeout_evidence_budget_exceeded"):
                preserve_evidence([record], root / "archive", policy="selective-v1")
            self.assertTrue((logs / "proof").exists())

    def test_selected_budget_is_aggregate_across_worktrees_before_any_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            records = []
            roots = []
            for number in (1, 2):
                root = base / f"worktree-{number}"
                logs = root / "logs"
                logs.mkdir(parents=True)
                (logs / "proof").write_text("same essential evidence")
                (logs / "evidence-retention.json").write_text(
                    json.dumps({"schemaVersion": 1, "keep": ["proof"], "discard": []})
                )
                records.append(register_directory(root, logs, "evidence"))
                roots.append(logs)
            single = sum(path.stat().st_size for path in roots[0].iterdir())
            with patch(
                "research_workbench_entrypoint.iteration_resources.EVIDENCE_ARCHIVE_MAX_BYTES",
                single + 1,
            ), patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaisesRegex(ResourceError, "closeout_evidence_budget_exceeded"):
                preserve_evidence(
                    records,
                    base / "archive",
                    policy="selective-v1",
                    task_id="retention-test",
                )
            self.assertTrue(all((logs / "proof").exists() for logs in roots))
            self.assertFalse((base / "archive").exists())

    def test_selected_budget_rejects_source_growth_after_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            records = []
            logs_roots = []
            for number in (1, 2):
                root = base / f"worktree-{number}"
                logs = root / "logs"
                logs.mkdir(parents=True)
                (logs / "proof").write_text("essential")
                (logs / "evidence-retention.json").write_text(
                    json.dumps({"schemaVersion": 1, "keep": ["proof"], "discard": []})
                )
                records.append(register_directory(root, logs, "evidence"))
                logs_roots.append(logs)
            original_total = sum(
                path.stat().st_size for logs in logs_roots for path in logs.iterdir()
            )
            original_manifest = resources.file_manifest
            first_root_reads = 0

            def growing_manifest(path):
                nonlocal first_root_reads
                if Path(path) == logs_roots[0]:
                    first_root_reads += 1
                    if first_root_reads == 2:
                        (logs_roots[1] / "proof").write_text("essential" + "x" * 11)
                return original_manifest(path)

            with patch(
                "research_workbench_entrypoint.iteration_resources.EVIDENCE_ARCHIVE_MAX_BYTES",
                original_total + 10,
            ), patch(
                "research_workbench_entrypoint.iteration_resources.file_manifest",
                side_effect=growing_manifest,
            ), patch(
                "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
            ), self.assertRaisesRegex(ResourceError, "closeout_evidence_source_changed"):
                preserve_evidence(
                    records, base / "archive", policy="selective-v1", task_id="retention-test"
                )
            self.assertTrue((logs_roots[1] / "proof").exists())

    def test_budget_is_aggregate_and_oldest_builder_is_reclaimed_first(self):
        driver = CacheDriver({"a": 18 * GIB, "b": 12 * GIB})
        report = cache_budget(driver, ["a", "b"], 20 * GIB)
        self.assertTrue(report["ok"])
        self.assertLessEqual(report["afterBytes"], 20 * GIB)
        self.assertEqual(driver.calls[0][0], "a")
        again = cache_budget(driver, ["a", "b"], 20 * GIB)
        self.assertTrue(again["ok"])
        self.assertEqual(len(driver.calls), 1)

    def test_in_use_cache_cannot_be_reported_as_cleaned(self):
        driver = CacheDriver({"a": 30 * GIB}, active={"a"})
        report = cache_budget(driver, ["a"], 20 * GIB)
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["afterBytes"], 30 * GIB)

    def test_duplicate_builder_does_not_double_count(self):
        with self.assertRaises(ResourceError):
            cache_budget(CacheDriver({"a": GIB}), ["a", "a"], 20 * GIB)

    def test_dependency_removal_keeps_reports_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            dep = root / "node_modules"
            dep.mkdir()
            (dep / "generated").write_text("rebuild")
            report = root / "report.md"
            report.write_text("evidence")
            record = register_directory(root, dep, "dependency")
            result = clean_dependencies([record], occupied=lambda _: False, tracked=lambda _: False)
            self.assertTrue(result["ok"])
            self.assertFalse(dep.exists())
            self.assertEqual(report.read_text(), "evidence")
            self.assertTrue(clean_dependencies([record], occupied=lambda _: False, tracked=lambda _: False)["ok"])

    def test_replaced_symlink_and_active_dependency_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            dep = root / ".venv"
            dep.mkdir()
            record = register_directory(root, dep, "dependency")
            self.assertFalse(clean_dependencies([record], occupied=lambda _: True, tracked=lambda _: False)["ok"])
            dep.rmdir()
            other = root / "business"
            other.mkdir()
            dep.symlink_to(other, target_is_directory=True)
            self.assertFalse(clean_dependencies([record], occupied=lambda _: False, tracked=lambda _: False)["ok"])
            self.assertTrue(other.exists())

    def test_arbitrary_or_tracked_directory_cannot_be_registered_or_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "reports").mkdir()
            with self.assertRaises(ResourceError):
                register_directory(root, root / "reports", "dependency")
            dep = root / "node_modules"
            dep.mkdir()
            record = register_directory(root, dep, "dependency")
            self.assertFalse(clean_dependencies([record], occupied=lambda _: False, tracked=lambda _: True)["ok"])
            self.assertTrue(dep.exists())


if __name__ == "__main__":
    unittest.main()
