"""Web-only startup: python -m uvicorn app.research_web.main:app --port 8088."""

import asyncio
import json
import mimetypes
import os
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.observability import get_logger, setup_logging

from .client import DSHClient, RuntimeFailure
from .service import ResearchService
from .store import Store, StoreError

log = get_logger(__name__)
UI = Path(__file__).parent / "ui"
ROOT = Path(os.environ.get("AF_RESEARCH_DATA", str(Path.home() / ".alphafoundry" / "research-web")))
UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".md", ".csv", ".xlsx"}


class NewSession(BaseModel):
    mode: Literal["fingpt", "claw"] = "fingpt"
    title: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_id: Literal["research"] = "research"


class Prompt(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=20)
    skill_id: str | None = None


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class Approval(BaseModel):
    decision: Literal["approve", "deny"]


class AnswerItem(BaseModel):
    id: str
    selected: list[str] = Field(default_factory=list, max_length=20)
    custom: str = Field(max_length=10000)


class Answers(BaseModel):
    answers: list[AnswerItem] = Field(min_length=1, max_length=20)


class ModelConfig(BaseModel):
    provider: Literal["deepseek-official"] = "deepseek-official"
    model: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._:/-]+$")
    api_key: str | None = Field(default=None, min_length=1, max_length=1024, repr=False)


def create_app(service: ResearchService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        setup_logging()
        active = service or ResearchService(
            DSHClient(os.environ.get("AF_DSH_URL", "http://127.0.0.1:3081")),
            Store(ROOT),
            owned=False,
            expected_cwd=ROOT / "runtime" / "work",
        )
        app.state.research = active
        await active.start()
        log.info("research_web_started", engine="dsh", legacy_services=False)
        try:
            yield
        finally:
            await active.close()

    app = FastAPI(title="AlphaFoundry Research Web", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def local_boundary(request, call_next):
        # Loopback app, no CORS. Stop drive-by requests / opaque sandbox origins.
        origin = request.headers.get("origin")
        own = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if (origin and origin != own) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(
                {"error": {"code": "origin_denied", "message": "跨站请求被拒绝"}}, status_code=403
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if "/preview" not in request.url.path:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'none'"
            )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RuntimeFailure)
    async def runtime_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": str(exc)}}, status_code=503)

    @app.exception_handler(StoreError)
    async def store_error(request, exc):
        return JSONResponse(
            {"error": {"code": "invalid_resource", "message": str(exc)}}, status_code=400
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default error includes rejected input, potentially an API key.
        return JSONResponse(
            {"error": {"code": "invalid_request", "message": "请求字段格式不正确"}}, status_code=422
        )

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        log.error("research_api_failed", path=request.url.path, error_type=type(exc).__name__)
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "请求处理失败，请查看本地日志"}},
            status_code=500,
        )

    def svc(request):
        return request.app.state.research

    @app.get("/api/research/runtime")
    async def runtime(request: Request):
        return await svc(request).runtime()

    @app.get("/api/research/models")
    async def models(request: Request):
        result = await svc(request).client.rpc("llm.models", {})
        return {
            "groups": [{**group, "provider": group["id"]} for group in result["groups"]],
            "failures": result["failures"],
        }

    @app.put("/api/research/runtime/model")
    async def configure_model(body: ModelConfig, request: Request):
        return await svc(request).configure_model(body.provider, body.model, body.api_key)

    @app.get("/api/research/workspaces")
    async def workspaces():
        return {"items": [{"id": "research", "name": "我的研究"}]}

    @app.get("/api/research/sessions")
    async def sessions(request: Request):
        service = svc(request)
        return {"items": await service.list_sessions()}

    @app.post("/api/research/sessions", status_code=201)
    async def create_session(body: NewSession, request: Request):
        return await svc(request).create(body.mode, body.title)

    @app.get("/api/research/sessions/{sid}")
    async def session(sid: str, request: Request):
        return await svc(request).detail(sid)

    @app.patch("/api/research/sessions/{sid}")
    async def rename(sid: str, body: Rename, request: Request):
        service = svc(request)
        await service.ensure_owned()
        row = service.store.session(sid)
        await service.client.rpc("session.rename", {"sessionId": sid, "title": body.title})
        row["title"] = body.title
        service.store.save()
        return service.summary(row)

    @app.post("/api/research/sessions/{sid}/messages", status_code=202)
    async def send(
        sid: str,
        body: Prompt,
        request: Request,
        idempotency_key: str = Header(min_length=8, max_length=128),
    ):
        if not body.text.strip():
            raise StoreError("问题不能为空")
        return await svc(request).send(
            sid, body.text, idempotency_key, body.attachment_ids, body.skill_id
        )

    @app.post("/api/research/sessions/{sid}/cancel")
    async def cancel(sid: str, request: Request):
        return await svc(request).cancel(sid)

    @app.post("/api/research/sessions/{sid}/approvals/{aid}")
    async def approve(sid: str, aid: str, body: Approval, request: Request):
        return await svc(request).approve(sid, aid, body.decision)

    @app.post("/api/research/sessions/{sid}/questions/{qid}")
    async def answer(sid: str, qid: str, body: Answers, request: Request):
        return await svc(request).answer(sid, qid, [item.model_dump() for item in body.answers])

    @app.post("/api/research/sessions/{sid}/upgrade")
    async def upgrade(sid: str, request: Request):
        service = svc(request)
        old = await service.detail(sid)
        new = await service.create("claw", old["title"])
        # Draft is carried into the composer, not submitted or forked across cwd boundaries.
        new["draft"] = "继续研究以下会话：\n" + "\n\n".join(
            f"{m['role']}: {m['text']}" for m in old["messages"]
        )
        for item in old["files"]:
            if item.get("kind") == "inputs":
                source = service.store.file_path(sid, item["id"])
                shutil.copyfile(source, service.store.directory(new["id"]) / "inputs" / source.name)
        new["attachments"] = service.store.files(new["id"])
        return new

    @app.get("/api/research/sessions/{sid}/events")
    async def events(sid: str, request: Request):
        service = svc(request)
        service.store.session(sid)

        async def stream():
            changed = asyncio.Event()
            service.listeners.add(changed)
            previous = None
            try:
                while not await request.is_disconnected():
                    changed.clear()
                    try:
                        detail = await service.detail(sid)
                        payload = json.dumps(detail, ensure_ascii=False)
                        if payload != previous:
                            yield f"event: snapshot\ndata: {payload}\n\n"
                            previous = payload
                    except RuntimeFailure as exc:
                        yield "event: runtime_error\ndata: " + json.dumps(
                            {"message": str(exc)}, ensure_ascii=False
                        ) + "\n\n"
                    try:
                        await asyncio.wait_for(changed.wait(), timeout=5)
                        await asyncio.sleep(0.12)
                    except TimeoutError:
                        yield ": heartbeat\n\n"
            finally:
                service.listeners.discard(changed)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.post("/api/research/sessions/{sid}/uploads")
    async def upload(sid: str, request: Request, files: list[UploadFile]):
        store = svc(request).store
        root = store.directory(sid) / "inputs"
        if root.is_symlink():
            raise StoreError("上传目录非法")
        if len(files) > 20:
            raise StoreError("每次最多上传 20 个文件")
        saved = set()
        for upload in files:
            name = Path(upload.filename or "").name
            extension = Path(name).suffix.lower()
            if extension not in UPLOAD_EXTENSIONS:
                raise StoreError("不支持的附件格式")
            safe_name = re.sub(r"[^\w.\-\u4e00-\u9fff]", "_", name)[:160]
            path = root / f"{uuid4().hex[:12]}-{safe_name}"
            size = 0
            try:
                with path.open("xb") as output:
                    os.chmod(path, 0o600)
                    while chunk := await upload.read(1024 * 1024):
                        size += len(chunk)
                        if size > 30 * 1024 * 1024:
                            raise StoreError("单文件超过 30 MB")
                        output.write(chunk)
                saved.add(path.name)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            finally:
                await upload.close()
        log.info("research_files_uploaded", session_id=sid, count=len(saved))
        return {"items": [file for file in store.files(sid) if file["name"] in saved]}

    @app.get("/api/research/sessions/{sid}/files")
    async def list_files(sid: str, request: Request):
        return {"items": svc(request).store.files(sid)}

    @app.get("/api/research/sessions/{sid}/files/{fid}/{action}")
    async def file(sid: str, fid: str, action: Literal["download", "preview"], request: Request):
        stream, name = svc(request).store.open_file(sid, fid)

        def chunks():
            try:
                while chunk := stream.read(65536):
                    yield chunk
            finally:
                stream.close()

        return StreamingResponse(
            chunks(),
            media_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
            headers={
                "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": f"{'attachment' if action == 'download' else 'inline'}; filename*=utf-8''{quote(name)}",
            },
        )

    @app.get("/api/research/skills")
    async def skills(request: Request):
        service = svc(request)
        rows = [row for row in service.store.data["sessions"].values() if row["created"]]
        if not rows:
            return {"items": []}
        result = await service.skill_catalog(rows[-1]["id"])
        return {"items": [{"id": skill["name"], **skill} for skill in result["skills"]]}

    if UI.exists():
        app.mount("/static", StaticFiles(directory=UI), name="static")

    @app.get("/")
    async def index():
        return FileResponse(UI / "index.html")

    return app


app = create_app()
