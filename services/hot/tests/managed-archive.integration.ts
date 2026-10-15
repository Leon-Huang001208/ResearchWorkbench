import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';

test('production manager backs up and restores managed PG then starts restored database',{timeout:120000},async()=>{
  const project=resolve(import.meta.dirname,'../../..');
  const probe=`import json,sys,tempfile,subprocess,os\nfrom pathlib import Path\nfrom research_workbench_entrypoint.hot import save_settings\nfrom research_workbench_entrypoint.hot_manager import HotManager\np=json.load(sys.stdin)\nhome=Path(tempfile.mkdtemp(prefix='rwb-hot-managed-archive-')).resolve()\nclass Credentials:\n def __init__(self): self.values={}\n def get_password(self,service,account): return self.values.get(account)\n def set_password(self,service,account,value): self.values[account]=value\nc=Credentials()\nsave_settings(Path(p['project']),home,{'enabled':True,'database':{'poolMax':1}})\nm=HotManager(Path(p['project']),home,c)\nm.setup()\ntry:\n backup=m.archive('backup')\n target='hot_restored_'+home.name.replace('-','_')[-20:]\n restored=m.archive('restore',Path(backup['directory']),target)\n config=m._config()\n config['database']['name']=target\n save_settings(m.project,home,config)\n started=m.start()\n stopped=m.stop()\n instance=json.loads((home/'hot/identity.json').read_text())['instanceId']\n print(json.dumps({'backup':backup['state'],'restore':restored['state'],'started':started['state'],'stopped':stopped['state'],'target':target,'home':str(home),'container':'rwb-hot-db-'+instance.replace('-','')[:16]}))\nfinally:\n m.stop()\n`;
  const result=await new Promise<string>((resolveProbe,reject)=>{
    const child=execFile('/opt/homebrew/bin/python3.12',['-c',probe],{cwd:project,
      env:{...process.env,RESEARCH_NODE_BINARY:process.execPath},timeout:110000},(error,stdout)=>error?reject(Error('hot_managed_archive_probe_failed')):resolveProbe(stdout));
    child.stdin!.end(JSON.stringify({project}));
  });
  const value=JSON.parse(result);
  assert.equal(value.backup,'backed_up');assert.equal(value.restore,'restored_paused');
  assert.equal(value.started,'initialized');assert.equal(value.stopped,'stopped');
  // Test container alone is stopped; database volume and archive are preserved.
  const run=promisify(execFile);await run('docker',['stop',value.container],{timeout:15000});
  console.log(JSON.stringify({evidence:'managed_archive',...value}));
});
