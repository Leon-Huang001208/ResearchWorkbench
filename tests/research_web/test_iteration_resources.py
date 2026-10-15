"""Iteration closeout must be bounded, recoverable and task-specific."""

import json
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from research_workbench_entrypoint.iteration_resources import (
    GIB,
    ResourceError,
    cache_budget,
    clean_dependencies,
    register_directory,
    preserve_evidence,
    task_resource_plan,
    occupied,
)
from research_workbench_entrypoint.iteration_cache import ManagedCaches


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
            with self.assertRaisesRegex(ResourceError,'fixture_gc_failure'):
                with driver.maintenance():
                    self.assertEqual(driver.current['HostConfig']['Memory'],2*GIB)
                    raise ResourceError('fixture_gc_failure')
            self.assertEqual(driver.current,original)
            self.assertFalse((root/'operation.lock').exists())

    def test_existing_builder_operation_lock_is_never_removed(self):
        from research_workbench_entrypoint.iteration_cache import operation_lock
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();lock=root/'operation.lock';lock.mkdir();(lock/'proof').write_text('active build')
            with self.assertRaises(ResourceError):
                with operation_lock(root):self.fail('must refuse concurrent maintenance')
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
                with patch('research_workbench_entrypoint.iteration_resources.shutil.copyfileobj', side_effect=partial_copy):
                    with self.assertRaises(OSError):
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
            with patch('research_workbench_entrypoint.iteration_resources.occupied',return_value=False), patch('research_workbench_entrypoint.iteration_resources.shutil.copyfileobj',side_effect=OSError('fixture')):
                with self.assertRaises(OSError): preserve_evidence([record],root/'archive')
            target=next((root/'archive').iterdir())/'logs/proof';target.write_text('changed')
            with patch('research_workbench_entrypoint.iteration_resources.occupied',return_value=False), self.assertRaises(ResourceError):
                preserve_evidence([record],root/'archive')
            self.assertEqual((logs/'proof').read_text(),'original')

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
