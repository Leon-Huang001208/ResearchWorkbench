"""Price imports are private, explicit and free of credential/model effects."""
import json
import tempfile
import unittest
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import io
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import redirect_stdout
from research_workbench_entrypoint.hot import dispatch
from research_workbench_entrypoint.hot import HotError
from research_workbench_entrypoint.hot_manager import HotManager

class Forbidden:
    def get_password(self,*args):
        raise AssertionError("must not resolve a credential")

class PricingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.project=self.root/"project";self.project.mkdir();self.home=self.root/"home"
        self.manager=HotManager(self.project,self.home,Forbidden())
        self.pricing=json.loads(Path("services/hot/pricing.deepseek.2026-10-09.json").read_text())
    def tearDown(self):
        self.tmp.cleanup()
    def prepare(self):
        self.manager.directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        identity=self.manager.directory/"identity.json";identity.write_text(json.dumps({"projectRoot":str(self.project),"instanceId":"00000000-0000-0000-0000-000000000001"}));identity.chmod(0o600)
    def reply(self,*args,**kwargs):
        pricing=json.loads(kwargs["input"])["pricing"]
        return SimpleNamespace(returncode=0,stdout=json.dumps({"state":"valid","pricing":pricing}).encode())
    def test_confirmation_precedes_resources_or_credentials(self):
        with self.assertRaisesRegex(HotError,"confirmation_required"):
            self.manager.import_pricing(self.pricing,verified=False,reason="verified")
        self.assertFalse(self.home.exists())
    def test_private_publication_reuse_and_new_revision_preserve_old_object(self):
        self.prepare()
        with patch.object(self.manager,"_state",return_value=None),patch.object(self.manager,"_config",return_value={"timezone":"Asia/Shanghai"}),patch("research_workbench_entrypoint.hot_pricing.subprocess.run",side_effect=self.reply):
            first=self.manager.import_pricing(self.pricing,verified=True,reason="verified source")
            replay=self.manager.import_pricing(self.pricing,verified=True,reason="verified source")
            self.assertTrue(replay["reused"]);self.assertEqual(first["pricingHash"],replay["pricingHash"])
            changed={**self.pricing,"outputMicrosPerMillion":2400000}
            later=self.manager.import_pricing(changed,verified=True,reason="new verified revision")
        folder=self.manager.directory/"pricing"
        self.assertTrue((folder/(first["pricingHash"]+".json")).exists());self.assertTrue((folder/(later["pricingHash"]+".json")).exists())
        self.assertEqual((folder/"2026-10-09.json").stat().st_mode&0o777,0o600)
    def test_running_node_refuses_before_validator(self):
        self.prepare()
        with patch.object(self.manager,"_state",return_value={"pid":123}),patch("research_workbench_entrypoint.hot_pricing.subprocess.run") as run:
            with self.assertRaisesRegex(HotError,"requires_stopped"):
                self.manager.import_pricing(self.pricing,verified=True,reason="verified")
            run.assert_not_called()
    def test_directory_fsync_failure_is_visible_and_replay_repairs_durability(self):
        self.prepare();original=os.fsync
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("synthetic fault")
            return original(fd)
        with patch.object(self.manager,"_state",return_value=None),patch.object(self.manager,"_config",return_value={"timezone":"Asia/Shanghai"}),patch("research_workbench_entrypoint.hot_pricing.subprocess.run",side_effect=self.reply):
            with patch("research_workbench_entrypoint.hot_pricing.os.fsync",side_effect=fail_directory):
                visible=self.manager.import_pricing(self.pricing,verified=True,reason="verified")
            self.assertEqual(visible["durability"],"unavailable");self.assertTrue(visible["pricingHash"])
            fixed=self.manager.import_pricing(self.pricing,verified=True,reason="verified")
            self.assertEqual(fixed["durability"],"confirmed");self.assertTrue(fixed["reused"])
    def test_failed_staging_cleans_temp_and_same_input_retries(self):
        self.prepare()
        with patch.object(self.manager,"_state",return_value=None),patch.object(self.manager,"_config",return_value={"timezone":"Asia/Shanghai"}),patch("research_workbench_entrypoint.hot_pricing.subprocess.run",side_effect=self.reply):
            with patch("research_workbench_entrypoint.hot_pricing.os.fsync",side_effect=OSError("synthetic write fault")):
                with self.assertRaisesRegex(HotError,"publish_unavailable"):
                    self.manager.import_pricing(self.pricing,verified=True,reason="verified")
            self.assertEqual(list((self.manager.directory/"pricing").iterdir()),[])
            self.assertEqual(self.manager.import_pricing(self.pricing,verified=True,reason="verified")["durability"],"confirmed")
    def test_actual_cli_validator_publication_and_replay_without_credentials(self):
        # The real validator requires today's date; this is a synthetic tariff,
        # not renewed provider pricing or a production authorization.
        self.pricing = {**self.pricing, "verifiedOn": datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()}
        project=Path.cwd().resolve();self.project=project;self.manager=HotManager(project,self.home,Forbidden());self.prepare()
        settings=self.manager.directory/"settings.json";settings.write_text(json.dumps({"projectRoot":str(project),"config":{"enabled":False}}));settings.chmod(0o600)
        file=self.root/"price.json";file.write_text(json.dumps(self.pricing))
        results=[]
        for _ in range(2):
            stream=io.StringIO()
            with patch("research_workbench_entrypoint.bootstrap.native_python",return_value=Path(sys.executable)),patch.dict(sys.modules,{"app.research_web.credential_backend":SimpleNamespace(SystemKeyringBackend=Forbidden)}),redirect_stdout(stream):
                code=dispatch(["--data-home",str(self.home),"model-pricing-import","--file",str(file),"--verify-official-pricing","--reason","CLI fixture using prior dated record","--json"],project)
            self.assertEqual(code,0);results.append(json.loads(stream.getvalue()))
        self.assertEqual(results[0]["pricingHash"],results[1]["pricingHash"]);self.assertTrue(results[1]["reused"])
    def test_real_validator_rejects_previous_day_without_publishing_or_credentials(self):
        self.project = Path.cwd().resolve()
        self.manager = HotManager(self.project, self.home, Forbidden())
        self.prepare()
        self.pricing = {**self.pricing, "verifiedOn": (datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)).isoformat()}
        with patch.object(self.manager, "_config", return_value={"timezone": "Asia/Shanghai"}):
            with self.assertRaisesRegex(HotError, "hot_pricing_invalid"):
                self.manager.import_pricing(self.pricing, verified=True, reason="synthetic stale tariff rejection")
        self.assertFalse((self.manager.directory / "pricing").exists())
