"""Bounded offline model administration; payloads stay on private child stdin."""
from __future__ import annotations
import hashlib
import json
import logging
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .hot import HotError, MAX_BYTES, _node, _no_alias, _read, save_settings

log=logging.getLogger(__name__)
KNOWN={"hot_model_control_invalid","hot_model_paid_authorization_required","hot_model_control_denied",
       "hot_model_control_requires_stopped","hot_model_control_instance_mismatch","hot_model_control_request_conflict",
       "hot_model_authorization_conflict","hot_model_termination_invalid","hot_model_controls_setup_required"}

def _object(value: object, keys: set[str]) -> dict:
    if not isinstance(value,dict) or set(value)!=keys:
        raise HotError("hot_model_control_invalid")
    return value

def _amount(value: object, maximum: int) -> int:
    if type(value) is not int or value<0 or value>maximum:
        raise HotError("hot_model_control_invalid")
    return value

def _scope(value: object) -> str:
    if not isinstance(value,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",value):
        raise HotError("hot_model_control_invalid")
    return value

def _validate(operation: str, params: dict) -> None:
    if operation=="authorize":
        _object(params,{"policy","authorizePaid"})
        if params["authorizePaid"] is not True:
            raise HotError("hot_model_paid_authorization_required")
        policy=_object(params["policy"],{"scopeId","maxCalls","maxTokens","maxCostMicros","daily"})
        _scope(policy["scopeId"])
        daily=_object(policy["daily"],{"maxCalls","maxTokens","maxCostMicros","timezone"})
        for record in (policy,daily):
            for field,maximum in (("maxCalls",10000),("maxTokens",10000000),("maxCostMicros",10000000000)):
                _amount(record[field],maximum)
        try:
            if not isinstance(daily["timezone"],str) or len(daily["timezone"])>80:
                raise ValueError()
            ZoneInfo(daily["timezone"])
        except (ZoneInfoNotFoundError,ValueError,TypeError):
            raise HotError("hot_model_control_invalid") from None
    elif operation=="terminate":
        _object(params,{"attemptId"})
        try:
            params["attemptId"]=str(UUID(params["attemptId"]))
        except (ValueError,TypeError,AttributeError):
            raise HotError("hot_model_control_invalid") from None
    elif operation=="attempts":
        if not isinstance(params,dict) or set(params)-{"scopeId","limit","offset"}:
            raise HotError("hot_model_control_invalid")
        if "scopeId" in params:
            _scope(params["scopeId"])
        if _amount(params.get("limit",50),50)==0:
            raise HotError("hot_model_control_invalid")
        _amount(params.get("offset",0),10000)
    else:
        raise HotError("hot_model_control_invalid")

def _write_journal(path: Path, value: dict) -> None:
    _no_alias(path)
    temp=path.with_name(".model-operation-"+uuid4().hex+".tmp")
    try:
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w") as stream:
            json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
        directory=os.open(path.parent,os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError:
        raise HotError("hot_model_journal_unavailable") from None
    finally:
        if temp.exists():
            temp.unlink()

def _event(project: Path, operation: str, state: str) -> None:
    path=project/"logs/hot/model-controls.jsonl";_no_alias(path)
    try:
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        with os.fdopen(fd,"w") as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:
                raise HotError("hot_model_log_unsafe")
            stream.write(json.dumps({"event":"hot_model_control","operation":operation,"state":state,"time":datetime.now(timezone.utc).isoformat()})+"\n")
            stream.flush()
    except OSError:
        raise HotError("hot_model_log_unavailable") from None

def _finish(manager, journal: Path, record: dict, state: str, *, mutable: bool, code: str | None=None) -> dict:
    """Post-dispatch bookkeeping never replaces a known/uncertain UUID receipt."""
    issues={}
    if mutable:
        try:
            _write_journal(journal,{**record,"state":state,**({"code":code} if code else {})})
        except (HotError,OSError):
            issues["persistence"]="unavailable"
    try:
        _event(manager.project,record["operation"],state)
    except (HotError,OSError):
        issues["logging"]="unavailable"
    return issues

def _confirmed(operation: str, response: object, params: dict, request_id: str | None) -> bool:
    if not isinstance(response,dict):
        return False
    if operation=="attempts":
        return isinstance(response.get("items"),list) and len(response["items"])<=50 and isinstance(response.get("budgets"),list) and len(response["budgets"])<=50
    if response.get("requestId")!=request_id:
        return False
    if operation=="terminate":
        return response.get("attemptId")==params["attemptId"] and (
            response.get("state")=="abandoned" and response.get("chargesRetained") is True
            or response.get("state")=="cancelled" and response.get("chargesRetained") is False and response.get("knownUnsent") is True
        )
    charged=response.get("charged")
    return response.get("state")=="authorized" and response.get("scopeId")==params["policy"]["scopeId"] and response.get("policy")==params["policy"] and isinstance(response.get("authorizationHash"),str) and bool(re.fullmatch(r"[a-f0-9]{64}",response["authorizationHash"])) and isinstance(charged,dict) and type(charged.get("calls")) is int and charged["calls"]>=0 and all(isinstance(charged.get(k),str) and charged[k].isascii() and charged[k].isdigit() for k in ("tokens","costMicros")) and type(response.get("paused")) is bool

def run_model_operation(manager, operation: str, params: dict, *, reason: str | None=None,
                        request_id: str | None=None, migration_user: str="postgres", migration_account: str="hot-migration-database") -> dict:
    _validate(operation,params)
    mutable=operation!="attempts"
    if mutable:
        if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:
            raise HotError("hot_model_control_invalid")
        try:
            request_id=str(UUID(request_id)) if request_id else str(uuid4())
        except (ValueError,TypeError,AttributeError):
            raise HotError("hot_model_control_invalid") from None
    if not isinstance(migration_user,str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,62}",migration_user) or not isinstance(migration_account,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",migration_account):
        raise HotError("hot_model_control_invalid")
    with manager._lock():
        if mutable and manager._state() is not None:
            raise HotError("hot_model_control_requires_stopped")
        config=manager._config()
        identity=_read(manager.directory/"identity.json",private=True)
        if identity.get("projectRoot")!=str(manager.project):
            raise HotError("hot_process_foreign")
        journal=manager.directory/"model-operation.json"
        operator="os-uid:"+str(os.getuid())
        canonical={"operation":operation,"parameters":params,"reason":reason.strip() if reason else None,"operator":operator,
                   "database":{k:v for k,v in config["database"].items() if config["database"]["mode"]!="managed" or k not in ("host","port")},"instanceId":identity["instanceId"]}
        try:
            encoded=json.dumps(canonical,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
            if len(encoded)>MAX_BYTES:
                raise ValueError()
        except (ValueError,UnicodeError,TypeError):
            raise HotError("hot_model_control_invalid") from None
        digest=hashlib.sha256(encoded).hexdigest()
        record={"version":1,"projectRoot":str(manager.project),"operation":operation,"requestId":request_id,"inputHash":digest,"state":"running"}
        if mutable and journal.exists():
            previous=_read(journal,private=True)
            if previous.get("projectRoot")!=str(manager.project) or previous.get("version")!=1 or previous.get("state") not in ("running","outcome_unknown","rejected","completed"):
                raise HotError("hot_model_journal_invalid")
            if previous.get("state") in ("running","outcome_unknown") and (previous.get("requestId")!=request_id or previous.get("inputHash")!=digest):
                raise HotError("hot_model_previous_outcome_unknown")
        if mutable and migration_user in (config["database"]["user"],config["database"]["controllerUser"]):
            raise HotError("hot_model_control_denied")
        account=config["database"]["secretRef"] if not mutable else ("hot-postgres-admin" if config["database"]["mode"]=="managed" else migration_account)
        payload={"config":config,"instanceId":identity["instanceId"],"operation":operation,"parameters":params,"password":manager._secret(account)}
        if mutable:
            if config["database"]["mode"]=="managed":
                from .hot_postgres import ManagedPostgres
                server=ManagedPostgres(manager.home,identity["instanceId"]).start(payload["password"])
                actual={key:server[key] for key in ("host","port")}
                if any(config["database"].get(key)!=value for key,value in actual.items()):
                    config["database"].update(actual)
                    saved=save_settings(manager.project,manager.home,config)
                    if saved.get("logging")=="unavailable":
                        raise HotError("hot_config_saved_log_unavailable")
                migration_user="postgres"
            payload.update(migrationUser=migration_user,controllerToken=manager._secret("rpc-controller"),requestId=request_id,reason=reason.strip(),operator=operator)
        _event(manager.project,operation,"started")
        if mutable:
            _write_journal(journal,record)
        try:
            result=subprocess.run([_node(),str(manager.project/"services/hot/scripts/model-control.ts")],input=json.dumps(payload,allow_nan=False),capture_output=True,text=True,timeout=30,cwd=manager.project)
            if len(result.stdout.encode())>MAX_BYTES:
                raise ValueError()
            envelope=json.loads(result.stdout)
            if envelope.get("protocol")!="rwb-hot-model/v1" or type(envelope.get("ok")) is not bool:
                raise ValueError()
            if envelope["ok"] is False and result.returncode and envelope.get("code") in KNOWN:
                issues=_finish(manager,journal,record,"rejected",mutable=mutable,code=envelope["code"])
                return {"state":"rejected","code":envelope["code"],"requestId":request_id,"operation":operation,**issues}
            response=envelope.get("response")
            if result.returncode or envelope["ok"] is not True or not _confirmed(operation,response,params,request_id):
                raise ValueError()
            issues=_finish(manager,journal,record,"completed",mutable=mutable)
            return {**response,**issues}
        except HotError:
            raise
        except (OSError,ValueError,TypeError,AttributeError,subprocess.SubprocessError):
            if not mutable:
                raise HotError("hot_model_operation_failed") from None
            issues=_finish(manager,journal,record,"outcome_unknown",mutable=True)
            log.warning("hot_model_control_outcome_unknown")
            return {"state":"outcome_unknown","code":"hot_model_control_outcome_unknown","requestId":request_id,"operation":operation,**issues}
