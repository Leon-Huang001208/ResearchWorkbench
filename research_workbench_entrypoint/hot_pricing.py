"""Explicit non-secret tariff publication; no credential, DB or model call."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import stat
from pathlib import Path
from uuid import uuid4
from .hot import HotError, MAX_BYTES, _node, _no_alias, _read
from .hot_model_controls import _event

def import_pricing(manager, value: dict, *, verified: bool, reason: str) -> dict:
    if verified is not True:
        raise HotError("hot_pricing_confirmation_required")
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000 or not isinstance(value,dict):
        raise HotError("hot_pricing_invalid")
    with manager._lock():
        if manager._state() is not None:
            raise HotError("hot_pricing_requires_stopped")
        config=manager._config();identity=_read(manager.directory/"identity.json",private=True)
        if identity.get("projectRoot")!=str(manager.project):
            raise HotError("hot_process_foreign")
        try:
            encoded=json.dumps({"pricing":value,"timezone":config["timezone"]},allow_nan=False).encode()
            if len(encoded)>MAX_BYTES:
                raise ValueError()
            result=subprocess.run([_node(),str(manager.project/"services/hot/scripts/check-pricing.ts")],input=encoded,capture_output=True,timeout=10,cwd=manager.project)
            if result.returncode or len(result.stdout)>MAX_BYTES:
                raise ValueError()
            checked=json.loads(result.stdout)
            if checked.get("state")!="valid" or checked.get("pricing")!=value:
                raise ValueError()
        except (OSError,ValueError,TypeError,AttributeError,subprocess.SubprocessError):
            raise HotError("hot_pricing_invalid") from None
        envelope={"version":1,"instanceId":identity["instanceId"],"projectRoot":str(manager.project),"pricing":value,
                  "verifiedBy":"os-uid:"+str(os.getuid()),"reason":reason.strip()}
        data=json.dumps(envelope,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
        digest=hashlib.sha256(data).hexdigest()
        folder=manager.directory/"pricing";_no_alias(folder);folder.mkdir(mode=0o700,exist_ok=True)
        info=folder.stat()
        if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
            raise HotError("hot_pricing_directory_unsafe")
        path=folder/(value["verifiedOn"]+".json");_no_alias(path)
        reused=False
        if path.exists():
            old=_read(path,private=True)
            if old.get("projectRoot")!=str(manager.project) or old.get("instanceId")!=identity["instanceId"]:
                raise HotError("hot_pricing_foreign")
            if old.get("pricing")==value:
                data=path.read_bytes();digest=hashlib.sha256(data).hexdigest();reused=True
        _event(manager.project,"pricing","started")
        archive=folder/(digest+".json")
        temporary=[];visible=reused;issues={}
        try:
            if archive.exists():
                _read(archive,private=True)
                if archive.read_bytes()!=data:
                    raise HotError("hot_pricing_archive_conflict")
            else:
                staged=folder/(".pricing-object-"+uuid4().hex+".tmp");temporary.append(staged)
                fd=os.open(staged,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,"wb") as stream:
                    stream.write(data);stream.flush();os.fsync(stream.fileno())
                # Publish only a complete durable object, never a partial final name.
                os.rename(staged,archive);temporary.remove(staged)
            if not reused:
                temp=folder/(".pricing-current-"+uuid4().hex+".tmp");temporary.append(temp)
                fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,"wb") as stream:
                    stream.write(data);stream.flush();os.fsync(stream.fileno())
                os.replace(temp,path);temporary.remove(temp);visible=True
            directory=os.open(folder,os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            if visible:
                return {"state":"pricing_imported","verifiedOn":value["verifiedOn"],"pricingHash":digest,"reused":reused,"durability":"unavailable",**issues}
            raise HotError("hot_pricing_publish_unavailable") from None
        finally:
            for temp in temporary:
                try:
                    if temp.exists():
                        temp.unlink()
                except OSError:
                    issues["cleanup"]="unavailable"
        response={"state":"pricing_imported","verifiedOn":value["verifiedOn"],"pricingHash":digest,"reused":reused,"durability":"confirmed",**issues}
        try:
            _event(manager.project,"pricing","completed")
        except HotError:
            response["logging"]="unavailable"
        return response
