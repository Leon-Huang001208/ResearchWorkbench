"""Authenticated selected research copies alongside the existing paused PG archive."""
import hashlib
import hmac
import json
import logging
import os
import re
import stat
import zipfile
from pathlib import Path
from uuid import UUID

from .hot import HotError, _no_alias

log = logging.getLogger(__name__)
LIMIT = 64 * 1024 * 1024
ROW_KEYS = {'id','mode','title','workspace_id','status','model','model_provider','created','hot_creation_state',
            'hot_origin','hot_delivery_key','delivery_key','files','updated_at','created_at','purpose'}

def private(path, directory=False, strict=True):
    _no_alias(path)
    value = path.stat()
    if value.st_uid != os.getuid() or (strict and stat.S_IMODE(value.st_mode) != (0o700 if directory else 0o600)) or (not directory and (not stat.S_ISREG(value.st_mode) or value.st_nlink != 1)):
        raise HotError('hot_joint_archive_unsafe')

def seal(value, token):
    return hmac.new(token.encode(), json.dumps(value,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()

def permitted(name, ids):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or str(p) != name:
        return False
    return any(name.startswith(f'sessions/{sid}/inputs/') or name.startswith(f'sessions/{sid}/outputs/')
               or name.startswith(f'.control/snapshots/{sid}/') for sid in ids)

def backup_research(home, archive, session_ids, token):
    """Never includes runtime auth, provider credentials, resources or unrelated sessions."""
    from app.research_web.store import Store, StoreError
    from app.research_web.datahub.security import directory, read_file
    home, archive = Path(home), Path(archive)
    private(archive, True)
    try:
        ids = list(dict.fromkeys(str(UUID(sid)) for sid in session_ids))
    except (ValueError, TypeError, AttributeError):
        log.warning('hot_joint_selection_rejected')
        raise HotError('hot_joint_selection_invalid') from None
    if not 1 <= len(ids) <= 10:
        raise HotError('hot_joint_selection_invalid')
    store = Store(home)
    rows, receipts, content = {}, {}, {}
    try:
        for sid in ids:
            row = store.session(sid)
            if row.get('purpose') != 'hot_research' or not row.get('hot_origin'):
                raise HotError('hot_joint_selection_invalid')
            rows[sid] = {key: value for key,value in row.items() if key in ROW_KEYS}
            key = row.get('hot_delivery_key') or row.get('delivery_key')
            if key and key.startswith('hot:'+row['hot_origin']['runId']+':'):
                receipt = store.data['receipts'].get(f'{sid}:{key}')
                if receipt:
                    receipts[f'{sid}:{key}'] = receipt
            for prefix in (f'sessions/{sid}/inputs',f'sessions/{sid}/outputs',f'.control/snapshots/{sid}'):
                parent = home / prefix
                if not parent.exists():
                    continue
                _no_alias(parent)
                for path in sorted(parent.rglob('*')):
                    _no_alias(path)
                    if path.is_dir():
                        continue
                    private(path, strict=False)
                    relative = path.relative_to(home).as_posix()
                    if not permitted(relative, ids) or path.stat().st_size > 16 * 1024 * 1024:
                        raise HotError('hot_joint_archive_limit')
                    with directory(home, path.relative_to(home).parts[:-1]) as fd:
                        content[relative] = read_file(fd, path.name, limit=16 * 1024 * 1024)
                    if len(content)>512 or sum(map(len,content.values()))>LIMIT:
                        raise HotError('hot_joint_archive_limit')
        metadata = json.dumps({'sessions':rows,'receipts':receipts},ensure_ascii=False).encode()
        if len(metadata)>700000:
            raise HotError('hot_joint_archive_limit')
        content['session-data.json'] = metadata
        target = archive/'research.zip'
        with target.open('xb') as raw:
            os.chmod(target,0o600)
            with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as package:
                for name,data in content.items():
                    package.writestr(name,data)
        body = {'version':1,'scope':'selected_research_snapshots','sessionIds':ids,
                'postgresManifestSha256':hashlib.sha256((archive/'manifest.json').read_bytes()).hexdigest(),
                'archiveSha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in content.items()}}
        with (archive/'research-manifest.json').open('x') as stream:
            os.chmod(stream.name,0o600);json.dump({**body,'proof':seal(body,token)},stream)
        log.info('hot_joint_archive_created sessions=%d files=%d',len(ids),len(content))
        return {'scope':body['scope'],'sessionIds':ids,'files':len(content),'archiveSha256':body['archiveSha256']}
    except (OSError,ValueError,KeyError,StoreError,zipfile.BadZipFile) as exc:
        log.warning('hot_joint_archive_failed type=%s',type(exc).__name__)
        raise HotError('hot_joint_archive_failed') from None

def verify_research(archive, token):
    archive=Path(archive);private(archive,True)
    for name in ['research.zip','research-manifest.json','manifest.json']:
        private(archive/name)
    try:
        if (archive/'research-manifest.json').stat().st_size>700000 or (archive/'research.zip').stat().st_size>LIMIT:
            raise ValueError()
        manifest=json.loads((archive/'research-manifest.json').read_bytes());proof=manifest.pop('proof')
        if not hmac.compare_digest(proof,seal(manifest,token)) or manifest['version']!=1 or manifest['scope']!='selected_research_snapshots':
            raise ValueError()
        ids=manifest['sessionIds']
        if not 1<=len(ids)<=10 or any(str(UUID(sid))!=sid for sid in ids):
            raise ValueError()
        if hashlib.sha256((archive/'manifest.json').read_bytes()).hexdigest()!=manifest['postgresManifestSha256']:
            raise ValueError()
        raw=(archive/'research.zip').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest['archiveSha256']:
            raise ValueError()
        content={};total=0
        with zipfile.ZipFile(archive/'research.zip') as package:
            entries=package.infolist()
            if len(entries)>513 or len({e.filename for e in entries})!=len(entries) or set(e.filename for e in entries)!=set(manifest['files']):
                raise ValueError()
            for entry in entries:
                if entry.filename!='session-data.json' and not permitted(entry.filename,ids):
                    raise ValueError()
                total+=entry.file_size
                if entry.file_size>16*1024*1024 or total>LIMIT or stat.S_ISLNK(entry.external_attr>>16):
                    raise ValueError()
                data=package.read(entry);expected=manifest['files'][entry.filename]
                if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
                    raise ValueError()
                content[entry.filename]=data
        metadata=json.loads(content.pop('session-data.json'))
        if set(metadata['sessions'])!=set(ids) or set(metadata)-{'sessions','receipts'}:
            raise ValueError()
        for sid,row in metadata['sessions'].items():
            if row.get('id')!=sid or set(row)-ROW_KEYS or row.get('purpose')!='hot_research' or row.get('mode') not in {'fingpt','claw'}:
                raise ValueError()
            origin=row.get('hot_origin')
            if not isinstance(origin,dict) or set(origin)!={'runId','instanceId','manifestHash'} or not re.fullmatch(r'[a-f0-9]{64}',origin['manifestHash']):
                raise ValueError()
            UUID(origin['runId']);UUID(origin['instanceId'])
            for relative in row.get('files',{}).values():
                if not isinstance(relative,str) or not permitted(f'sessions/{sid}/{relative}',ids):
                    raise ValueError()
        for key in metadata['receipts']:
            if not any(re.fullmatch(re.escape(sid+':hot:'+metadata['sessions'][sid]['hot_origin']['runId']+':')+r'[a-f0-9]{64}',key) for sid in ids):
                raise ValueError()
        return manifest,metadata,content
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
        log.warning('hot_joint_archive_rejected type=%s',type(exc).__name__)
        raise HotError('hot_joint_archive_invalid') from None

def preflight_research_restore(home, archive, token):
    manifest,metadata,content=verify_research(archive,token)
    home=Path(home);_no_alias(home)
    existing=json.loads((home/'index.json').read_bytes()) if (home/'index.json').exists() else {'sessions':{}}
    attempt={'version':1,'archiveSha256':manifest['archiveSha256'],'targetSha256':hashlib.sha256(str(home.absolute()).encode()).hexdigest()}
    expected={**attempt,'proof':seal(attempt,token)}
    journal=home/'.control/hot-joint-restore.json';_no_alias(journal)
    replay=False
    if journal.exists():
        private(journal)
        if json.loads(journal.read_bytes())!=expected:
            raise HotError('hot_joint_restore_conflict')
        replay=True
    if home.exists() and not replay:
        raise HotError('hot_joint_restore_target_not_fresh')
    if replay and (set(existing['sessions'])-set(manifest['sessionIds']) or set(existing.get('receipts',{}))-set(metadata['receipts'])):
        raise HotError('hot_joint_restore_conflict')
    if replay:
        if any(value!=metadata['receipts'][key] for key,value in existing.get('receipts',{}).items()):
            raise HotError('hot_joint_restore_conflict')
        allowed=set(content)|{'index.json','.control/hot-joint-restore.json'}
        directories={str(parent) for name in allowed for parent in Path(name).parents if str(parent)!='.'}
        for path in home.rglob('*'):
            _no_alias(path)
            relative=path.relative_to(home).as_posix()
            if relative not in (directories if path.is_dir() else allowed):
                raise HotError('hot_joint_restore_conflict')
    for sid in manifest['sessionIds']:
        if not replay and (sid in existing['sessions'] or (home/'sessions'/sid).exists() or (home/'.control/snapshots'/sid).exists()):
            raise HotError('hot_joint_restore_conflict')
        if sid in existing['sessions']:
            row=existing['sessions'][sid]
            if not row.get('restored_snapshot') or {key:value for key,value in row.items() if key in ROW_KEYS}!=metadata['sessions'][sid]:
                raise HotError('hot_joint_restore_conflict')
        for prefix in (f'sessions/{sid}/inputs',f'sessions/{sid}/outputs',f'.control/snapshots/{sid}'):
            parent=home/prefix
            if parent.exists():
                _no_alias(parent)
                for path in parent.rglob('*'):
                    _no_alias(path)
                    if path.is_dir():continue
                    relative=path.relative_to(home).as_posix()
                    if relative not in content or path.read_bytes()!=content[relative]:
                        raise HotError('hot_joint_restore_conflict')
    return manifest,metadata,content

def restore_research(home, archive, token):
    """Restore into absent session paths; retain historic receipts, never start Runtime."""
    from app.research_web.store import Store, StoreError
    from app.research_web.datahub.security import directory, write_new, sync_directory
    manifest,metadata,content=preflight_research_restore(home,archive,token)
    home=Path(home);_no_alias(home)
    if not home.exists():
        home.mkdir(parents=True,mode=0o700)
    store=Store(home)
    initial_index=store.index.read_bytes() if store.index.exists() else None
    try:
        attempt={'version':1,'archiveSha256':manifest['archiveSha256'],'targetSha256':hashlib.sha256(str(home.absolute()).encode()).hexdigest()}
        with directory(home,('.control',),create=True) as fd:
            if 'hot-joint-restore.json' not in os.listdir(fd):
                write_new(fd,'hot-joint-restore.json',json.dumps({**attempt,'proof':seal(attempt,token)}).encode());sync_directory(fd)
        for sid in manifest['sessionIds']:
            row=metadata['sessions'][sid]
            if row['id']!=sid or set(row)-ROW_KEYS or row.get('purpose')!='hot_research':
                raise HotError('hot_joint_archive_invalid')
        for name,data in content.items():
            parts=Path(name).parts
            with directory(home, parts[:-1], create=True) as fd:
                if parts[-1] not in os.listdir(fd):
                    write_new(fd,parts[-1],data);sync_directory(fd)
        for sid,row in metadata['sessions'].items():
            row['restored_snapshot']=True
            store.data['sessions'][sid]=row
        store.data['receipts'].update(metadata['receipts'])
        if (store.index.read_bytes() if store.index.exists() else None)!=initial_index:
            raise HotError('hot_joint_restore_conflict')
        store.save()
        log.info('hot_joint_snapshot_restored sessions=%d',len(manifest['sessionIds']))
        return {'state':'restored_snapshots_paused','sessionIds':manifest['sessionIds'],'nativeExecution':'not_restored','files':len(content)}
    except (OSError,ValueError,KeyError,StoreError) as exc:
        log.warning('hot_joint_snapshot_restore_failed type=%s',type(exc).__name__)
        raise HotError('hot_joint_restore_failed') from None
