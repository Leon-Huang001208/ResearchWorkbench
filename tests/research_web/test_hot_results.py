"""Existing reports survive Native failure; GET neither starts nor sends research."""
import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.research_web.store import Store, StoreError
from app.research_web.delivery import Delivery
from app.research_web.hot_results import artifacts, research_results, refresh_research_result
from app.research_web.hot_service import HotWebError

class HotResultsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        store = Store(Path(self.temp.name).resolve())
        self.row = store.create('fingpt', 'Owned report')
        self.origin = {'runId':str(uuid4()), 'instanceId':str(uuid4()), 'manifestHash':'a'*64}
        self.row.update(created=True,purpose='hot_research',hot_origin=self.origin)
        self.run = {**self.origin,'runId':self.origin['runId'],'sessionId':self.row['id'],'evidenceManifestHash':'a'*64,'revision':2,'state':'failed','errorCode':'hot_model_budget_exhausted'}
        self.service = SimpleNamespace(client=SimpleNamespace(history=AsyncMock()),store=store, delivery=Delivery(store), workbench_lock=asyncio.Lock(), ensure_owned=AsyncMock(), detail=AsyncMock())
        self.key='hot:'+self.origin['runId']+':'+'c'*64
        self.run['deliveryKey']=self.key
        self.row['hot_delivery_key']=self.key
        store.reserve(self.row['id'],self.key,'b'*64,{'status':'completed','required_formats':['md'],'files':[]})
        path = store.directory(self.row['id'])/'outputs'/'report.md';path.write_text('# Real file\n')
        item = next(x for x in store.files(self.row['id']) if x['kind']=='outputs')
        self.service.delivery.current(self.row['id'])['files']=[{**item,'valid':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
        self.path = path
        self.hot = SimpleNamespace(call=AsyncMock(return_value=self.run))
    async def asyncTearDown(self):
        self.temp.cleanup()
    async def test_failed_run_has_verified_report_and_get_only_reads(self):
        result=await research_results(self.service,self.hot)
        row=result['items'][0]
        self.assertEqual((row['runState'],row['deliveryState']),('failed','completed'))
        self.assertTrue(row['artifacts'][0]['verified'])
        self.hot.call.assert_awaited_once_with('research_run',self.origin['runId'])
        self.service.detail.assert_not_awaited()
    async def test_offline_state_retains_report_but_never_claims_live_status(self):
        self.hot.call.side_effect=HotWebError('hot_service_stopped','stopped')
        row=(await research_results(self.service,self.hot))['items'][0]
        self.assertFalse(row['stateVerified']);self.assertEqual(row['runState'],'unavailable')
        self.assertEqual(row['deliveryState'],'completed')
    async def test_changed_output_cannot_reuse_saved_success(self):
        self.path.write_text('# changed\n')
        row=(await research_results(self.service,self.hot))['items'][0]
        self.assertEqual(row['deliveryState'],'available')
        self.assertTrue(row['artifacts'][0]['changed'])

    async def test_valid_reports_over_aggregate_display_limit_remain_completed(self):
        self.path.write_bytes(b'x' * (12 * 1024 * 1024))
        docx = self.path.with_suffix('.docx')
        docx.write_bytes(b'y' * (8 * 1024 * 1024))
        delivery = self.service.delivery.current(self.row['id'])
        delivery.update(required_formats=['md', 'docx'], files=[
            {**item, 'valid': True, 'sha256': hashlib.sha256(
                (self.service.store.directory(self.row['id']) / 'outputs' / item['name']).read_bytes()).hexdigest()}
            for item in self.service.store.files(self.row['id']) if item['kind'] == 'outputs'])
        self.assertEqual(artifacts(self.service, self.row['id'], self.key)['deliveryState'], 'completed')

    async def test_sixth_saved_file_can_satisfy_required_format(self):
        self.path.unlink()
        for i in range(5):
            (self.path.parent / f'{i}.md').write_text('small markdown')
        (self.path.parent / 'z.docx').write_bytes(b'prevalidated receipt fixture')
        delivery = self.service.delivery.current(self.row['id'])
        delivery.update(required_formats=['md', 'docx'], files=[
            {**item, 'valid': True, 'sha256': hashlib.sha256(
                (self.path.parent / item['name']).read_bytes()).hexdigest()}
            for item in self.service.store.files(self.row['id']) if item['kind'] == 'outputs'])
        self.assertEqual(artifacts(self.service, self.row['id'], self.key)['deliveryState'], 'completed')
    async def test_foreign_pg_mapping_not_shown_as_owned_execution(self):
        self.hot.call.return_value={**self.run,'instanceId':str(uuid4())}
        row=(await research_results(self.service,self.hot))['items'][0]
        self.assertFalse(row['stateVerified'])
    async def test_explicit_observation_preserves_failure_despite_completed_report(self):
        self.run['state']='running'
        self.service.client.history.return_value=[{'event':{'seq':1,'type':'user/message','data':{'content':[{'type':'text','text':'[RWB_HOT_EXECUTION:'+self.key+']'}]}}},{'event':{'seq':2,'type':'turn/end','data':{'reason':{'kind':'error'}}}}]
        async def call(operation,*args,**kwargs):
            if operation=='research_run':return self.run
            self.assertEqual(operation,'advance_research_run')
            self.assertEqual(args[0]['state'],'failed')
            self.assertEqual(args[0]['expectedRevision'],2)
            return {**self.run,'state':'failed'}
        self.hot.call.side_effect=call
        result=await refresh_research_result(self.service,self.hot,self.run['runId'])
        self.assertEqual((result['state'],result['deliveryState']),('failed','completed'))

    async def test_later_delivery_and_turn_cannot_overwrite_original_run(self):
        self.row['delivery_key']='later'
        self.service.store.data['receipts'][self.row['id']+':later']={'delivery':{'status':'incomplete','required_formats':['docx'],'files':[]}}
        self.assertEqual((await research_results(self.service,self.hot))['items'][0]['deliveryState'],'completed')
        self.run['state']='running'
        self.service.client.history.return_value=[{'event':{'seq':1,'type':'user/message','data':{'content':[{'type':'text','text':'[RWB_HOT_EXECUTION:'+self.key+']'}]}}},{'event':{'seq':2,'type':'turn/end','data':{'reason':{'kind':'completed'}}}},{'event':{'seq':3,'type':'user/message','data':{'content':[{'type':'text','text':'later'}]}}},{'event':{'seq':4,'type':'turn/end','data':{'reason':{'kind':'error'}}}}]
        async def call(operation,*args,**kwargs):
            if operation=='research_run':return self.run
            self.assertEqual(args[0]['state'],'completed')
            return {**self.run,'state':'completed'}
        self.hot.call.side_effect=call
        self.assertEqual((await refresh_research_result(self.service,self.hot,self.run['runId']))['state'],'completed')
    async def test_changed_report_is_verified_before_completed_state_write(self):
        self.run['state']='running';self.path.write_text('changed')
        self.service.client.history.return_value=[{'event':{'seq':1,'type':'user/message','data':{'content':[{'type':'text','text':'[RWB_HOT_EXECUTION:'+self.key+']'}]}}},{'event':{'seq':2,'type':'turn/end','data':{'reason':{'kind':'completed'}}}}]
        async def call(operation,*args,**kwargs):
            if operation=='research_run':return self.run
            self.assertEqual(args[0]['state'],'failed')
            return {**self.run,'state':'failed'}
        self.hot.call.side_effect=call
        self.assertEqual((await refresh_research_result(self.service,self.hot,self.run['runId']))['state'],'failed')

    async def test_pending_report_uses_existing_validator_before_marking_complete(self):
        self.run['state']='running'
        delivery=self.service.delivery.current(self.row['id'])
        delivery.update(status='pending',baseline={},marker='[RESEARCH_TASK:test]',missing_formats=['md'],reasons=[])
        self.service.client.history.return_value=[{'event':{'seq':1,'type':'user/message','data':{'content':[{'type':'text','text':'[RWB_HOT_EXECUTION:'+self.key+'] [RESEARCH_TASK:test]'}]}}},{'event':{'seq':2,'type':'turn/end','data':{'reason':{'kind':'completed'}}}}]
        async def call(operation,*args,**kwargs):
            if operation=='research_run':return self.run
            self.assertEqual(args[0]['state'],'completed')
            return {**self.run,'state':'completed'}
        self.hot.call.side_effect=call
        result=await refresh_research_result(self.service,self.hot,self.run['runId'])
        self.assertEqual((result['state'],result['deliveryState']),('completed','completed'))
    async def test_pending_old_task_is_not_failed_or_certified_from_new_task(self):
        self.run['state']='running';self.row['delivery_key']='later'
        self.service.store.data['receipts'][self.row['id']+':'+self.key]['delivery']['status']='pending'
        self.service.client.history.return_value=[{'event':{'seq':1,'type':'user/message','data':{'content':[{'type':'text','text':'[RWB_HOT_EXECUTION:'+self.key+']'}]}}},{'event':{'seq':2,'type':'turn/end','data':{'reason':{'kind':'completed'}}}}]
        result=await refresh_research_result(self.service,self.hot,self.run['runId'])
        self.assertEqual(result['state'],'running')
        self.hot.call.assert_awaited_once_with('research_run',self.run['runId'])
