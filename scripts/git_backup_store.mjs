/** Private, append-only backup payloads. Never borrows objects from a working repository. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';

const HASH = /^[a-f0-9]{64}$/;
const OID = /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/;
const POINT = /^[a-f0-9]{8}-[a-f0-9-]{27,40}$/;
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
const fail = code => { throw Object.assign(new Error(code), {code}); };
function syncDirectory(directory) {
  const fd=fs.openSync(directory,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
  try{if(!fs.fstatSync(fd).isDirectory())fail('BACKUP_DIRECTORY_INVALID');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
}
function syncFile(filename) {
  const fd=fs.openSync(filename,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
  try{const s=fs.fstatSync(fd);if(!s.isFile() || s.nlink!==1)fail('BACKUP_FILE_INVALID');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  syncDirectory(path.dirname(filename));
}

export function safeDirectory(directory, create = false, privateMode = true) {
  const absolute = path.resolve(directory);
  for (let p = absolute; p !== path.dirname(p); p = path.dirname(p)) {
    const s = fs.lstatSync(p, {throwIfNoEntry: false});
    if (s?.isSymbolicLink() || s && !s.isDirectory()) fail('BACKUP_DIRECTORY_INVALID');
  }
  if (create && !fs.existsSync(absolute)) {
    const missing=[];for(let p=absolute;!fs.existsSync(p);p=path.dirname(p))missing.push(p);
    fs.mkdirSync(absolute, {recursive:true, mode:0o700});
    for(const p of missing.reverse()){syncDirectory(p);syncDirectory(path.dirname(p));}
  }
  const s = fs.lstatSync(absolute, {throwIfNoEntry:false});
  if (!s?.isDirectory() || s.uid !== process.getuid() || s.mode & (privateMode ? 0o077 : 0o022)) fail('BACKUP_DIRECTORY_NOT_PRIVATE');
  return absolute;
}
export function readFileChecked(filename) {
  safeDirectory(path.dirname(filename),false,false);
  const fd = fs.openSync(filename, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const before=fs.fstatSync(fd);
    if (!before.isFile() || before.nlink!==1 || before.uid!==process.getuid()) fail('BACKUP_FILE_INVALID');
    const bytes=fs.readFileSync(fd), after=fs.fstatSync(fd), current=fs.lstatSync(filename);
    if (after.size!==before.size || after.mtimeMs!==before.mtimeMs || after.ctimeMs!==before.ctimeMs || current.ino!==before.ino || current.dev!==before.dev || !current.isFile() || current.nlink!==1) fail('BACKUP_FILE_CHANGED');
    return bytes;
  } finally {fs.closeSync(fd);}
}
export function fileHash(filename) {
  safeDirectory(path.dirname(filename),false,false);
  const fd=fs.openSync(filename,fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const before=fs.fstatSync(fd), h=crypto.createHash('sha256'), buffer=Buffer.allocUnsafe(1024*1024);
    if (!before.isFile() || before.nlink!==1 || before.uid!==process.getuid()) fail('BACKUP_FILE_INVALID');
    let n; while((n=fs.readSync(fd,buffer,0,buffer.length,null)))h.update(buffer.subarray(0,n));
    const after=fs.fstatSync(fd),current=fs.lstatSync(filename);
    if(after.size!==before.size || after.mtimeMs!==before.mtimeMs || after.ctimeMs!==before.ctimeMs || current.ino!==before.ino || current.dev!==before.dev || !current.isFile() || current.nlink!==1)fail('BACKUP_FILE_CHANGED');
    return h.digest('hex');
  } finally {fs.closeSync(fd);}
}
export function writePrivate(filename, bytes) {
  safeDirectory(path.dirname(filename),true);
  if(fs.lstatSync(filename,{throwIfNoEntry:false}))fail('BACKUP_TARGET_EXISTS');
  const temporary=path.join(path.dirname(filename),'.write-'+crypto.randomUUID());
  const fd=fs.openSync(temporary,fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
  try {
    fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);
    if(fs.lstatSync(filename,{throwIfNoEntry:false}))fail('BACKUP_TARGET_EXISTS');
    fs.renameSync(temporary,filename);syncDirectory(path.dirname(filename));
  } finally {fs.closeSync(fd);if(fs.existsSync(temporary))fs.unlinkSync(temporary);}
}
function copyChecked(source,destination,expected) {
  if(fileHash(source)!==expected)fail('BACKUP_HASH_MISMATCH');
  safeDirectory(path.dirname(destination),true,false);
  if(fs.existsSync(destination) || fs.lstatSync(destination,{throwIfNoEntry:false}))fail('BACKUP_TARGET_EXISTS');
  // A clone is independent of future source writes and has nlink=1; hardlinks/alternates are forbidden.
  const temporary=path.join(path.dirname(destination),'.copy-'+crypto.randomUUID());
  try {
    fs.copyFileSync(source,temporary,fs.constants.COPYFILE_FICLONE|fs.constants.COPYFILE_EXCL);
    fs.chmodSync(temporary,0o600);
    if(fileHash(temporary)!==expected || fileHash(source)!==expected)fail('BACKUP_HASH_MISMATCH');
    syncFile(temporary);
    if(fs.lstatSync(destination,{throwIfNoEntry:false}))fail('BACKUP_TARGET_EXISTS');
    fs.renameSync(temporary,destination);syncDirectory(path.dirname(destination));
  }finally{if(fs.existsSync(temporary))fs.unlinkSync(temporary);}
}
export function withBackupLock(root,callback) {
  safeDirectory(root,true);
  const lock=path.join(root,'.backup.lock');
  try {fs.mkdirSync(lock,{mode:0o700});} catch(error) {if(error.code==='EEXIST')fail('BACKUP_STORE_LOCKED');throw error;}
  const before=fs.lstatSync(lock);
  let held=true;
  const assertHeld=()=>{
    const current=fs.lstatSync(lock,{throwIfNoEntry:false});
    if(!held || !current?.isDirectory() || current.ino!==before.ino || current.dev!==before.dev || current.isSymbolicLink())fail('BACKUP_LOCK_CHANGED');
  };
  try{return callback(assertHeld);}finally{
    assertHeld();held=false;
    fs.rmdirSync(lock);
  }
}
function run(gitPath, repository,args,{input,inputFd,outputFd}={}) {
  const env={...process.env};
  for(const key of ['GIT_ALTERNATE_OBJECT_DIRECTORIES','GIT_OBJECT_DIRECTORY','GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE'])delete env[key];
  const result=spawnSync(gitPath,['-c','gc.auto=0','-c','maintenance.auto=false','-C',repository,...args],{
    input,stdio:inputFd!==undefined?[inputFd,'pipe','pipe']:outputFd!==undefined?['pipe',outputFd,'pipe']:undefined,maxBuffer:64*1024*1024,
    env
  });
  if(result.error || result.status!==0)fail('BACKUP_OBJECT_COMMAND_FAILED');
  return result.stdout?.toString('utf8').trim() ?? '';
}
function storage(root,key) {
  if(!HASH.test(key))fail('BACKUP_REPOSITORY_INVALID');
  return path.join(root,'.v2-store','git',key);
}
function blobPath(root,hash) {
  if(!HASH.test(hash))fail('BACKUP_HASH_INVALID');
  return path.join(root,'.v2-store','files',hash.slice(0,2),hash.slice(2));
}
function relativeFile(directory,relative) {
  if(typeof relative!=='string' || path.isAbsolute(relative) || relative.split('/').some(x=>!x || x==='.' || x==='..'))fail('BACKUP_PATH_INVALID');
  return path.join(directory,relative);
}
function packObjects(gitPath,repository,ids,destination) {
  writePrivate(destination,'');const fd=fs.openSync(destination,'r+');
  try{run(gitPath,repository,['pack-objects','--stdout'],{input:ids.join('\n')+'\n',outputFd:fd});fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
}
function importPack(root,key,source,expected,gitPath,scratch) {
  const directory=storage(root,key);safeDirectory(directory,true);
  const objectMap=new Map(),descriptors=new Map();
  for(const name of fs.readdirSync(directory).filter(x=>/^[a-f0-9]{64}\.json$/.test(x))) {
    const meta=JSON.parse(readFileChecked(path.join(directory,name)));
    if(!HASH.test(meta.id) || !Array.isArray(meta.objects) || !meta.objects.every(x=>OID.test(x)))fail('BACKUP_PACK_METADATA_INVALID');
    descriptors.set(meta.id,meta);
    for(const oid of meta.objects)if(!objectMap.has(oid))objectMap.set(oid,meta.id);
  }
  const repository=path.join(scratch,'import-'+crypto.randomUUID()+'.git');
  const p=spawnSync(gitPath,['-c','gc.auto=0','init','--bare',repository],{encoding:'utf8'});
  if(p.error || p.status!==0)fail('BACKUP_OBJECT_COMMAND_FAILED');
  const input=path.join(repository,'objects/pack/input.pack');
  copyChecked(source,input,expected);
  run(gitPath,repository,['index-pack',input]);
  const index=input.replace(/\.pack$/,'.idx');
  const rows=run(gitPath,repository,['verify-pack','-v',index]).split('\n');
  const objects=rows.map(x=>x.split(' ')[0]).filter(x=>OID.test(x));
  if(!objects.length)fail('BACKUP_PACK_EMPTY');
  const missing=objects.filter(x=>!objectMap.has(x));
  if(missing.length) {
    const incoming=path.join(scratch,'incoming-'+crypto.randomUUID()+'.pack');
    packObjects(gitPath,repository,missing,incoming);
    run(gitPath,repository,['index-pack',incoming]);
    const incomingIndex=incoming.replace(/\.pack$/,'.idx');
    const id=fileHash(incoming),indexHash=fileHash(incomingIndex);
    const meta={id,indexHash,objects:missing};
    if(!fs.existsSync(path.join(directory,id+'.json'))) {
      for(const [from,to,hash] of [[incoming,id+'.pack',id],[incomingIndex,id+'.idx',indexHash]]) {
        const destination=path.join(directory,to);
        if(fs.existsSync(destination)){if(fileHash(destination)!==hash)fail('BACKUP_HASH_MISMATCH');}
        else copyChecked(from,destination,hash);
      }
      writePrivate(path.join(directory,id+'.json'),JSON.stringify(meta)+'\n');
    }
    descriptors.set(id,meta);for(const oid of missing)objectMap.set(oid,id);
  }
  const ids=[...new Set(objects.map(x=>objectMap.get(x)))].sort();
  return ids.map(id=>({id,indexHash:descriptors.get(id).indexHash}));
}
export function readManifest(directory) {
  const bytes=readFileChecked(path.join(directory,'manifest.json'));
  const manifest=JSON.parse(bytes);
  if(![1,2].includes(manifest.schemaVersion) || manifest.restoreVerified!==true || manifest.metadataSemantics && manifest.metadataSemantics!=='as-of-capture' || !manifest.refs || !Array.isArray(manifest.worktrees) || !Array.isArray(manifest.files))fail('BACKUP_MANIFEST_INVALID');
  if(manifest.schemaVersion===2 && (!HASH.test(manifest.repositoryKey) || !Array.isArray(manifest.gitPacks) || !manifest.gitPacks.length))fail('BACKUP_MANIFEST_INVALID');
  if(manifest.schemaVersion===2) {
    const seal=JSON.parse(readFileChecked(path.join(directory,'seal.json')));
    if(seal.manifestSha256!==digest(bytes) || manifest.stateHash!==fingerprint(manifest,manifest.protection))fail('BACKUP_METADATA_MISMATCH');
  }
  for(const value of Object.values({...manifest.refs,...(manifest.preservationRefs??{}),...(manifest.additionalBundleRefs??{})}))if(!OID.test(value))fail('BACKUP_MANIFEST_INVALID');
  for(const saved of manifest.worktrees) {
    if(!OID.test(saved.head) || typeof saved.path!=='string' || !path.isAbsolute(saved.path) || !Array.isArray(saved.tracked) || !Array.isArray(saved.untracked) || !(manifest.schemaVersion===1 && saved.index===undefined) && !HASH.test(saved.index) || !HASH.test(saved.staged) || !HASH.test(saved.unstaged))fail('BACKUP_MANIFEST_INVALID');
    for(const item of [...saved.tracked,...saved.untracked]) {
      relativeFile(directory,item.path);
      if(!['file','missing','symlink'].includes(item.type) || item.type!=='missing' && !HASH.test(item.sha256) || item.type==='symlink' && typeof item.link!=='string')fail('BACKUP_MANIFEST_INVALID');
    }
  }
  return {manifest:{...manifest,preservationRefs:manifest.preservationRefs??{}},hash:digest(bytes)};
}
export function materializeV2(directory,manifest,callback) {
  const root=path.dirname(directory),temporary=fs.mkdtempSync(path.join(directory,'.restore-input-'));
  try {
    safeDirectory(temporary);
    for(const row of manifest.files) {
      if(!HASH.test(row.sha256))fail('BACKUP_HASH_INVALID');
      copyChecked(blobPath(root,row.sha256),relativeFile(temporary,row.path),row.sha256);
    }
    return callback(temporary);
  }finally{fs.rmSync(temporary,{recursive:true});}
}
export function hydrateV2(directory,manifest,bare) {
  const root=path.dirname(directory),pool=storage(root,manifest.repositoryKey);
  for(const row of manifest.gitPacks) {
    if(!HASH.test(row.id) || !HASH.test(row.indexHash))fail('BACKUP_PACK_METADATA_INVALID');
    // Retain Git's SHA-1 pack filename convention; the full SHA-256 remains bound in the manifest.
    const name='pack-'+row.id.slice(0,40);
    copyChecked(path.join(pool,row.id+'.pack'),path.join(bare,'objects/pack',name+'.pack'),row.id);
    copyChecked(path.join(pool,row.id+'.idx'),path.join(bare,'objects/pack',name+'.idx'),row.indexHash);
  }
}
export function fingerprint(snapshot,protection='ordinary') {
  return digest(JSON.stringify({refs:snapshot.refs,registeredWorktrees:snapshot.registeredWorktrees,worktrees:snapshot.worktrees,preservationRefs:snapshot.preservationRefs??{},protection}));
}
export function findReusable(root,key,stateHash) {
  if(!fs.existsSync(root))return null;
  safeDirectory(root);
  for(const name of fs.readdirSync(root).filter(x=>POINT.test(x)).sort()) {
    const directory=path.join(root,name);
    if(!fs.existsSync(path.join(directory,'manifest.json')))continue;
    const {manifest}=readManifest(directory);
    if(manifest.schemaVersion===2 && manifest.repositoryKey===key && manifest.stateHash===stateHash)return {directory,manifest};
  }
  return null;
}
export function convertToV2(directory,key,{gitPath,now=Date.now(),protection='ordinary',verify,stateHash,afterVerified,afterPendingWritten}={}) {
  const root=path.dirname(directory),{manifest:legacy,hash:sourceHash}=readManifest(directory);
  if(legacy.schemaVersion===2){verify(directory,legacy);return {directory,reused:true,restoreVerified:true,fsck:'PASS'};}
  const temporary=fs.mkdtempSync(path.join(root,'.migrate-'));
  try {
    const meta=legacy.files.find(x=>x.path==='objects.pack');
    if(!meta)fail('BACKUP_OBJECT_PACK_MISSING');
    let packs=importPack(root,key,path.join(directory,'objects.pack'),meta.sha256,gitPath,temporary);
    const bundle=legacy.files.find(x=>x.path==='commits.bundle');let additionalBundleRefs={};
    if(bundle) {
      const bundlePath=path.join(directory,'commits.bundle');
      if(fileHash(bundlePath)!==bundle.sha256)fail('BACKUP_HASH_MISMATCH');
      const repository=path.join(temporary,'bundle.git');
      run(gitPath,temporary,['init','--bare',repository]);
      run(gitPath,repository,['bundle','verify',bundlePath]);
      const refs=run(gitPath,repository,['bundle','unbundle',bundlePath]);
      additionalBundleRefs=Object.fromEntries(refs.split('\n').map(line=>line.split(' ')).filter(([oid,ref])=>OID.test(oid) && (ref?.startsWith('refs/') || ref==='HEAD') && legacy.refs[ref]!==oid).map(([oid,ref])=>[ref,oid]));
      for(const name of fs.readdirSync(path.join(repository,'objects/pack')).filter(x=>x.endsWith('.pack'))) {
        const file=path.join(repository,'objects/pack',name);
        packs.push(...importPack(root,key,file,fileHash(file),gitPath,temporary));
      }
      packs=[...new Map(packs.map(x=>[x.id,x])).values()].sort((a,b)=>a.id.localeCompare(b.id));
    }
    const files=legacy.files.filter(x=>!['objects.pack','commits.bundle'].includes(x.path));
    for(const row of legacy.files) {
      if(fileHash(relativeFile(directory,row.path))!==row.sha256)fail('BACKUP_HASH_MISMATCH');
      if(['objects.pack','commits.bundle'].includes(row.path))continue;
      const target=blobPath(root,row.sha256);
      if(fs.existsSync(target)){if(fileHash(target)!==row.sha256)fail('BACKUP_HASH_MISMATCH');syncFile(target);}
      else copyChecked(relativeFile(directory,row.path),target,row.sha256);
    }
    const createdAt=legacy.createdAt??new Date(fs.statSync(path.join(directory,'manifest.json')).mtimeMs).toISOString();
    let manifest={...legacy,schemaVersion:2,metadataSemantics:'as-of-capture',repositoryKey:key,gitPacks:packs,additionalBundleRefs,files,createdAt,verifiedAt:new Date(now).toISOString(),protection,stateHash:stateHash??fingerprint(legacy,protection),migration:{sourceManifestSha256:sourceHash,sourceArtifacts:legacy.files}};
    const prepared=path.join(directory,'manifest-v2.pending.json');
    if(fs.existsSync(prepared)) {
      const pending=JSON.parse(readFileChecked(prepared));
      const stable=value=>{const {verifiedAt,...rest}=value;return JSON.stringify(rest);};
      if(stable(pending)!==stable(manifest))fail('BACKUP_MIGRATION_PENDING_CHANGED');
      manifest=pending;
    }
    // Verify from shared payloads alone before removing even one v1 artifact.
    verify(directory,manifest);
    afterVerified?.();
    if(readManifest(directory).hash!==sourceHash)fail('BACKUP_MANIFEST_CHANGED');
    const encoded=JSON.stringify(manifest)+'\n';
    if(!fs.existsSync(prepared))writePrivate(prepared,encoded);
    afterPendingWritten?.();
    const seal=path.join(directory,'seal.json'),certificate={manifestSha256:digest(encoded)};
    if(fs.existsSync(seal)) {
      if(JSON.parse(readFileChecked(seal)).manifestSha256!==certificate.manifestSha256)fail('BACKUP_METADATA_MISMATCH');
    }else writePrivate(seal,JSON.stringify(certificate)+'\n');
    // Atomic metadata switch retains existing receipt paths. v1 payloads are dispensable only afterwards.
    if(readManifest(directory).hash!==sourceHash)fail('BACKUP_MANIFEST_CHANGED');
    fs.renameSync(prepared,path.join(directory,'manifest.json'));
    syncDirectory(directory);syncDirectory(root);
    finishMigration(directory,manifest);
    return {directory,restoreVerified:true,fsck:'PASS',schemaVersion:2};
  }finally{fs.rmSync(temporary,{recursive:true});}
}
export function finishMigration(directory,manifest) {
  if(manifest.schemaVersion!==2 || !manifest.migration) return;
  const removable=manifest.migration.sourceArtifacts;
  if(!Array.isArray(removable))fail('BACKUP_MIGRATION_METADATA_INVALID');
  for(const row of removable) {
    const file=relativeFile(directory,row.path);
    if(fs.existsSync(file) && fileHash(file)!==row.sha256)fail('BACKUP_MIGRATION_ARTIFACT_CHANGED');
  }
  for(const row of removable) {
    const relative=row.path;
    const file=relativeFile(directory,relative),s=fs.lstatSync(file,{throwIfNoEntry:false});
    if(!s)continue;
    if(!s.isFile() || s.isSymbolicLink() || s.nlink!==1 || s.uid!==process.getuid())fail('BACKUP_MIGRATION_ARTIFACT_CHANGED');
    if(fileHash(file)!==row.sha256)fail('BACKUP_MIGRATION_ARTIFACT_CHANGED');
    fs.unlinkSync(file);
  }
  syncDirectory(directory);
}
export function listPoints(root) {
  if(!fs.existsSync(root))return [];
  safeDirectory(root);
  return fs.readdirSync(root).filter(x=>POINT.test(x)).map(id=>{
    const directory=path.join(root,id);
    try{return {id,directory,...readManifest(directory)};}catch(error){
      let protectedLegacyFailure=false;
      try {
        const draft=JSON.parse(readFileChecked(path.join(directory,'manifest-draft.json'))),failure=JSON.parse(readFileChecked(path.join(directory,'failure-status.json')));
        protectedLegacyFailure=!fs.existsSync(path.join(directory,'manifest.json')) && !fs.existsSync(path.join(directory,'seal.json')) && !fs.existsSync(path.join(directory,'manifest-v2.pending.json')) && draft.schemaVersion===1 && !draft.restoreVerified && !draft.gitPacks && !draft.repositoryKey && failure.status==='FAIL' && failure.restoreVerified===false;
      }catch{/* Unrecognized records remain protected and block collection. */}
      return {id,directory,error:error.code??'BACKUP_MANIFEST_INVALID',protectedLegacyFailure};
    }
  });
}
export function sweepPayloads(root,points) {
  // Unknown/draft points may be interrupted writers: never collect their possible shared payloads.
  if(points.some(x=>x.error && !x.protectedLegacyFailure || fs.existsSync(path.join(x.directory,'manifest-v2.pending.json'))))return {status:'blocked',reason:'unknown_or_pending_recovery_point'};
  const files=new Set(),packs=new Set();
  for(const {manifest:m} of points.filter(x=>x.manifest?.schemaVersion===2)) {
    for(const f of m.files)files.add(f.sha256);
    for(const p of m.gitPacks)packs.add(m.repositoryKey+'/'+p.id);
  }
  const store=path.join(root,'.v2-store');let removed=0;
  for(const directory of [path.join(store,'files'),path.join(store,'git')]) {
    if(!fs.existsSync(directory))continue;
    safeDirectory(directory);
    for(const group of fs.readdirSync(directory)) {
      const parent=path.join(directory,group);safeDirectory(parent);
      for(const name of fs.readdirSync(parent)) {
        const file=path.join(parent,name),s=fs.lstatSync(file);
        if(!s.isFile() || s.nlink!==1 || s.isSymbolicLink())fail('BACKUP_STORE_ARTIFACT_INVALID');
        let keep;
        if(path.basename(directory)==='files') {
          if(!HASH.test(group+name))fail('BACKUP_STORE_ARTIFACT_INVALID');
          keep=files.has(group+name);
        }else {
          const match=/^([a-f0-9]{64})\.(pack|idx|json)$/.exec(name);
          if(!HASH.test(group) || !match)fail('BACKUP_STORE_ARTIFACT_INVALID');
          keep=packs.has(group+'/'+match[1]);
        }
        if(!keep){fs.unlinkSync(file);removed++;}
      }
      syncDirectory(parent);
    }
  }
  return {status:'complete',removedFiles:removed};
}
export const repositoryKey=commonDirectory=>digest(path.resolve(commonDirectory));
