"""Offline controls validate before credential lookup and preserve uncertain UUIDs."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from research_workbench_entrypoint.hot import HotError
from research_workbench_entrypoint.hot_manager import HotManager

POLICY={"scopeId":"authorized","maxCalls":20,"maxTokens":20000,"maxCostMicros":1000000,
        "daily":{"maxCalls":20,"maxTokens":20000,"maxCostMicros":1000000,"timezone":"Asia/Shanghai"}}
RID="00000000-0000-0000-0000-000000000001"

class ForbiddenCredentials:
    def get_password(self,*args):
        raise AssertionError("must not resolve")

class ModelControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.project=self.root/"project";self.project.mkdir();self.home=self.root/"home"
        self.manager=HotManager(self.project,self.home,ForbiddenCredentials())
    def tearDown(self):
        self.temp.cleanup()
    def prepared(self):
        self.manager.directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        path=self.manager.directory/"identity.json";path.write_text(json.dumps({"projectRoot":str(self.project),"instanceId":RID}));path.chmod(0o600)
        cfg={"enabled":False,"database":{"mode":"external","user":"worker","controllerUser":"controller","secretRef":"worker","controllerSecretRef":"controller","name":"db","schema":"hot"}}
        return patch.object(self.manager,"_config",return_value=cfg)
    def test_missing_paid_authorization_and_bad_policy_precede_any_credentials_or_resources(self):
        with self.assertRaisesRegex(HotError,"paid_authorization_required"):
            self.manager.model_operation("authorize",{"policy":POLICY,"authorizePaid":False},reason="approved",request_id=RID)
        bad={**POLICY,"maxCalls":True}
        with self.assertRaisesRegex(HotError,"control_invalid"):
            self.manager.model_operation("authorize",{"policy":bad,"authorizePaid":True},reason="approved",request_id=RID)
        self.assertFalse(self.home.exists())
    def test_running_service_refuses_offline_mutation_before_credentials(self):
        with self.prepared(),patch.object(self.manager,"_state",return_value={"pid":123}):
            with self.assertRaisesRegex(HotError,"requires_stopped"):
                self.manager.model_operation("authorize",{"policy":POLICY,"authorizePaid":True},reason="approved",request_id=RID)
    def test_timeout_retains_exact_uuid_and_rejects_different_retry(self):
        with self.prepared(),patch.object(self.manager,"_secret",return_value="a"*64),patch.object(self.manager,"_state",return_value=None),patch("research_workbench_entrypoint.hot_model_controls.subprocess.run",side_effect=subprocess.TimeoutExpired("node",30)):
            result=self.manager.model_operation("authorize",{"policy":POLICY,"authorizePaid":True},reason="approved",request_id=RID)
        self.assertEqual(result["state"],"outcome_unknown");self.assertEqual(result["requestId"],RID)
        with self.prepared(),patch.object(self.manager,"_state",return_value=None):
            with self.assertRaisesRegex(HotError,"previous_outcome_unknown"):
                self.manager.model_operation("authorize",{"policy":POLICY,"authorizePaid":True},reason="approved",request_id="00000000-0000-0000-0000-000000000002")
    def test_malformed_success_cannot_confirm_termination(self):
        reply=SimpleNamespace(returncode=0,stdout=json.dumps({"protocol":"rwb-hot-model/v1","ok":True,"response":{"state":"abandoned","requestId":RID,"chargesRetained":False}}))
        with self.prepared(),patch.object(self.manager,"_secret",return_value="a"*64),patch.object(self.manager,"_state",return_value=None),patch("research_workbench_entrypoint.hot_model_controls.subprocess.run",return_value=reply):
            result=self.manager.model_operation("terminate",{"attemptId":RID},reason="approved",request_id=RID)
        self.assertEqual(result["state"],"outcome_unknown");self.assertEqual(result["requestId"],RID)
    def test_post_dispatch_journal_and_log_errors_keep_generated_uuid(self):
        from research_workbench_entrypoint import hot_model_controls as module
        original_journal=module._write_journal;original_event=module._event
        for state in ("completed","outcome_unknown","rejected"):
            for failing in ("journal","log"):
                with self.subTest(state=state,failing=failing):
                    def journal(path,value):
                        if failing=="journal" and value["state"]==state:
                            raise HotError("hot_model_journal_unavailable")
                        return original_journal(path,value)
                    def event(project,operation,current):
                        if failing=="log" and current==state:
                            raise HotError("hot_model_log_unavailable")
                        return original_event(project,operation,current)
                    def run(*args,**kwargs):
                        request=json.loads(kwargs["input"]);request_id=request["requestId"]
                        if state=="outcome_unknown":
                            raise subprocess.TimeoutExpired("node",30)
                        envelope={"protocol":"rwb-hot-model/v1","ok":state!="rejected"}
                        if state=="rejected":
                            envelope["code"]="hot_model_termination_invalid"
                        else:
                            envelope["response"]={"state":"abandoned","requestId":request_id,"attemptId":RID,"scopeId":"authorized","chargesRetained":True}
                        return SimpleNamespace(returncode=int(state=="rejected"),stdout=json.dumps(envelope))
                    journal_path=self.manager.directory/"model-operation.json"
                    if journal_path.exists():
                        journal_path.unlink()
                    with self.prepared(),patch.object(self.manager,"_secret",return_value="a"*64),patch.object(self.manager,"_state",return_value=None),patch.object(module,"_write_journal",side_effect=journal),patch.object(module,"_event",side_effect=event),patch.object(module.subprocess,"run",side_effect=run):
                        result=self.manager.model_operation("terminate",{"attemptId":RID},reason="approved")
                    self.assertTrue(result["requestId"]);self.assertEqual(result["persistence" if failing=="journal" else "logging"],"unavailable")
    def test_pending_control_blocks_start_before_any_credentials(self):
        with self.prepared():
            path=self.manager.directory/"model-operation.json";path.write_text(json.dumps({"projectRoot":str(self.project),"state":"outcome_unknown"}));path.chmod(0o600)
            with self.assertRaisesRegex(HotError,"previous_outcome_unknown"):
                self.manager.start()
    def test_managed_mutation_can_recover_cold_database_but_read_never_starts_it(self):
        config={"enabled":False,"database":{"mode":"managed","user":"worker","controllerUser":"controller","secretRef":"worker","controllerSecretRef":"controller","name":"db","schema":"hot","host":"127.0.0.1","port":55432}}
        def run(*args,**kwargs):
            payload=json.loads(kwargs["input"])
            if payload["operation"]=="attempts":
                response={"items":[],"budgets":[]}
            else:
                self.assertEqual(payload["config"]["database"]["port"],55499)
                response={"state":"abandoned","requestId":payload["requestId"],"attemptId":RID,"scopeId":"authorized","chargesRetained":True}
            return SimpleNamespace(returncode=0,stdout=json.dumps({"protocol":"rwb-hot-model/v1","ok":True,"response":response}))
        with self.prepared(),patch.object(self.manager,"_config",return_value=config),patch.object(self.manager,"_secret",return_value="a"*64),patch.object(self.manager,"_state",return_value=None),patch("research_workbench_entrypoint.hot_model_controls.save_settings",return_value={"logging":"available"}) as save,patch("research_workbench_entrypoint.hot_postgres.ManagedPostgres.start",return_value={"host":"127.0.0.1","port":55499}) as start,patch("research_workbench_entrypoint.hot_model_controls.subprocess.run",side_effect=run):
            self.manager.model_operation("attempts",{})
            start.assert_not_called()
            self.manager.model_operation("terminate",{"attemptId":RID},reason="approved",request_id=RID)
            start.assert_called_once()
            save.assert_called_once()
