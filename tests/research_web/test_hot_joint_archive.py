"""Selected research backup is sealed, bounded and restored without execution."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from app.research_web.store import Store
from research_workbench_entrypoint.hot import HotError
from research_workbench_entrypoint.hot_joint_archive import backup_research, restore_research, verify_research

class JointArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.home=self.root/'source';self.store=Store(self.home)
        self.row=self.store.create('fingpt','Selected report');self.sid=self.row['id'];self.run=str(uuid4())
        self.row.update(purpose='hot_research',created=True,hot_origin={'runId':self.run,'instanceId':str(uuid4()),'manifestHash':'a'*64},hot_delivery_key='hot:'+self.run+':'+'b'*64)
        self.store.reserve(self.sid,self.row['hot_delivery_key'],'c'*64,{'status':'completed','files':[],'required_formats':['md']})
        self.path=self.store.directory(self.sid)/'outputs/report.md';self.path.write_text('# Selected\n')
        (self.store.directory(self.sid)/'inputs/note.json').write_text('{"source":"selected"}')
        self.store.files(self.sid);self.store.save()
        (self.home/'runtime').mkdir();(self.home/'runtime/auth.json').write_text('secret sentinel excluded')
        self.archive=self.root/'archive';self.archive.mkdir(mode=0o700)
        p=self.archive/'manifest.json';p.write_text('{"scope":"hot_schema"}');p.chmod(0o600)
        self.token='a'*64
    def tearDown(self):self.temp.cleanup()
    def test_exact_files_receipt_and_old_identity_restore_but_auth_is_excluded(self):
        result=backup_research(self.home,self.archive,[self.sid],self.token)
        manifest,metadata,files=verify_research(self.archive,self.token)
        self.assertNotIn('runtime/auth.json',files)
        self.assertEqual(metadata['sessions'][self.sid]['hot_origin'],self.row['hot_origin'])
        target=self.root/'restored';restored=restore_research(target,self.archive,self.token)
        self.assertEqual(restored['nativeExecution'],'not_restored')
        self.assertEqual((target/'sessions'/self.sid/'outputs/report.md').read_bytes(),self.path.read_bytes())
        self.assertIn(self.sid+':'+self.row['hot_delivery_key'],Store(target).data['receipts'])
        self.assertEqual(restore_research(target,self.archive,self.token)['state'],'restored_snapshots_paused')
        (target/'sessions'/self.sid/'outputs/foreign.md').write_text('unrelated')
        with self.assertRaisesRegex(HotError,'conflict'):restore_research(target,self.archive,self.token)
    def test_tamper_or_wrong_signer_rejects_before_target_is_created(self):
        backup_research(self.home,self.archive,[self.sid],self.token)
        with self.assertRaises(HotError):verify_research(self.archive,'different')
        with (self.archive/'research.zip').open('ab') as stream:stream.write(b'tamper')
        target=self.root/'rejected'
        with self.assertRaises(HotError):restore_research(target,self.archive,self.token)
        self.assertFalse(target.exists())
    def test_symlinked_source_is_rejected(self):
        bad=self.home/'sessions'/self.sid/'inputs/bad';bad.symlink_to(self.home/'runtime/auth.json')
        with self.assertRaises(HotError):backup_research(self.home,self.archive,[self.sid],self.token)

    def test_invalid_session_id_has_stable_error_and_no_archive(self):
        with self.assertRaisesRegex(HotError, 'hot_joint_selection_invalid'):
            backup_research(self.home, self.archive, ['invalid'], self.token)
        self.assertFalse((self.archive / 'research.zip').exists())

    def test_metadata_counts_toward_uncompressed_limit_before_success(self):
        # The selected bytes fit, but the session metadata does not.
        with patch('research_workbench_entrypoint.hot_joint_archive.LIMIT', 100):
            with self.assertRaisesRegex(HotError, 'hot_joint_archive_limit'):
                backup_research(self.home, self.archive, [self.sid], self.token)
        self.assertFalse((self.archive / 'research-manifest.json').exists())

    def test_zip_overhead_cannot_publish_an_unrestorable_manifest(self):
        # A stored ZIP is larger than its payload even when the payload fits.
        import zipfile
        backup_research(self.home, self.archive, [self.sid], self.token)
        with zipfile.ZipFile(self.archive / 'research.zip') as package:
            limit = sum(entry.file_size for entry in package.infolist())
        second = self.root / 'zip-limit'; second.mkdir(mode=0o700)
        (second / 'manifest.json').write_bytes((self.archive / 'manifest.json').read_bytes())
        original = zipfile.ZipFile
        def stored(raw, mode, compression):
            return original(raw, mode, zipfile.ZIP_STORED)
        with patch('research_workbench_entrypoint.hot_joint_archive.LIMIT', limit), patch.object(zipfile, 'ZipFile', side_effect=stored):
            with self.assertRaisesRegex(HotError, 'hot_joint_archive_limit'):
                backup_research(self.home, second, [self.sid], self.token)
        self.assertFalse((second / 'research-manifest.json').exists())

    def test_interrupted_copy_resumes_only_its_sealed_attempt(self):
        from unittest.mock import patch
        from app.research_web.datahub import security
        backup_research(self.home,self.archive,[self.sid],self.token)
        target=self.root/'interrupted';original=security.write_new;calls=0
        def interrupted(*args):
            nonlocal calls
            calls+=1
            if calls==3:raise OSError('synthetic write interruption')
            return original(*args)
        with patch.object(security,'write_new',side_effect=interrupted):
            with self.assertRaises(HotError):restore_research(target,self.archive,self.token)
        self.assertEqual(restore_research(target,self.archive,self.token)['state'],'restored_snapshots_paused')
        self.assertEqual((target/'sessions'/self.sid/'outputs/report.md').read_bytes(),self.path.read_bytes())

    def test_existing_unrelated_store_is_never_merged_or_overwritten(self):
        backup_research(self.home,self.archive,[self.sid],self.token)
        target=self.root/'existing';other=Store(target);other.create('fingpt','Unrelated');before=(target/'index.json').read_bytes()
        with self.assertRaisesRegex(HotError,'target_not_fresh'):restore_research(target,self.archive,self.token)
        self.assertEqual((target/'index.json').read_bytes(),before)

    def test_index_change_during_copy_is_preserved_and_refuses_save(self):
        from unittest.mock import patch
        from app.research_web.datahub import security
        backup_research(self.home,self.archive,[self.sid],self.token)
        target=self.root/'concurrent';original=security.write_new;calls=0
        concurrent=b'{"sessions":{"unrelated":{"id":"unrelated"}},"receipts":{}}'
        def changed(*args):
            nonlocal calls
            calls+=1
            result=original(*args)
            if calls==2:(target/'index.json').write_bytes(concurrent)
            return result
        with patch.object(security,'write_new',side_effect=changed):
            with self.assertRaisesRegex(HotError,'conflict'):restore_research(target,self.archive,self.token)
        self.assertEqual((target/'index.json').read_bytes(),concurrent)

    def test_replay_refuses_changed_receipt_and_unrelated_new_runtime_files(self):
        backup_research(self.home,self.archive,[self.sid],self.token)
        target=self.root/'audited';restore_research(target,self.archive,self.token)
        store=Store(target);key=self.sid+':'+self.row['hot_delivery_key']
        store.data['receipts'][key]['new_audit']='preserve this';store.save();before=(target/'index.json').read_bytes()
        with self.assertRaisesRegex(HotError,'conflict'):restore_research(target,self.archive,self.token)
        self.assertEqual((target/'index.json').read_bytes(),before)
        other=self.root/'runtime-new';restore_research(other,self.archive,self.token)
        (other/'runtime').mkdir();(other/'runtime/auth.json').write_text('foreign runtime')
        with self.assertRaisesRegex(HotError,'conflict'):restore_research(other,self.archive,self.token)
