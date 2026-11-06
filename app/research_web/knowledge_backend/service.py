"""WeKnora material facade; current user authorization precedes every upstream read."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from functools import wraps
from uuid import uuid4

from core.observability import get_logger

from ..credential_backend import default_credential_backend
from ..store import StoreError
from .client import WeKnoraClient
from .configuration import checked_origin
from .storage import KnowledgeStore, canonical, digest, fail

log = get_logger(__name__)
RELEASE = "v0.9.0"
SOURCE_COMMIT = "f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7"
OPERATION_TIMEOUT = 60


def bounded(operation):
    @wraps(operation)
    async def execute(*args, **kwargs):
        try:
            async with asyncio.timeout(OPERATION_TIMEOUT):
                return await operation(*args, **kwargs)
        except TimeoutError:
            fail("knowledge_operation_timeout", 504)

    return execute


def chunk_fingerprint(chunks):
    keys = ("chunk_id", "document_id", "kb_id", "content", "chunk_index", "start_at", "end_at")
    rows = [{key: row[key] for key in keys} for row in chunks]
    if not rows or len({row["chunk_id"] for row in rows}) != len(rows):
        fail("knowledge_chunk_manifest_invalid", 502)
    return digest(canonical(sorted(rows, key=lambda row: row["chunk_id"])))


def timestamp(value: str):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError("zone")
        return result
    except (ValueError, TypeError, AttributeError):
        fail("knowledge_source_time_unknown", 422)


class KnowledgeService:
    def __init__(self, store, *, credentials=None, client_factory=WeKnoraClient, origin=None):
        self.store = KnowledgeStore(store.root)
        self.credentials = credentials
        self.client_factory = client_factory
        self.origin = (
            origin if origin is not None else os.environ.get("RESEARCH_WEKNORA_ORIGIN", "")
        )
        self.namespace = "ResearchWorkbench.WeKnora." + self.store.owner
        self.lock = asyncio.Lock()

    def status(self):
        binding = self.store.binding()
        try:
            origin = checked_origin(self.origin) if self.origin else None
        except StoreError:
            origin = None
        return {
            "enabled": origin is not None,
            "configured": binding is not None,
            "expected_release": RELEASE,
            "expected_source_commit": SOURCE_COMMIT,
            "workspace_id": binding["workspace_id"] if binding else None,
            "user_id": binding["user_id"] if binding else None,
            "connectivity": "not_verified",
            "live_acceptance": "NOT_RUN",
            "report_acceptance": "NOT_RUN",
            "management_url": origin,
            "credential_cleanup_pending": bool(binding and binding.get("retained_credentials")),
        }

    def _credentials(self):
        return self.credentials if self.credentials is not None else default_credential_backend()

    def _client(self, binding=None):
        if not self.origin:
            fail("knowledge_backend_disabled", 409)
        checked_origin(self.origin)
        binding = binding or self.store.binding()
        if not binding or binding.get("origin") != self.origin:
            fail("knowledge_binding_required", 401)
        try:
            token = self._credentials().get_password(self.namespace, binding["credential_ref"])
        except Exception:  # noqa: BLE001 - credential backends do not share exception types.
            fail("knowledge_credentials_unavailable", 503)
        if not token:
            fail("knowledge_reauthentication_required", 401)
        return self.client_factory(self.origin, token, binding["workspace_id"]), binding

    async def _authorized(self):
        client, binding = self._client()
        identity = await client.identity()
        if (
            identity.get("user_id") != binding["user_id"]
            or identity.get("workspace_id") != binding["workspace_id"]
        ):
            fail("knowledge_identity_changed", 403)
        return client, binding

    async def _still_authorized(self, binding):
        _, current = await self._authorized()
        if current != binding:
            fail("knowledge_binding_changed", 409)

    @bounded
    async def bind(self, token: str, workspace_id: str):
        if not self.origin:
            fail("knowledge_backend_disabled", 409)
        async with self.lock:
            client = self.client_factory(self.origin, token, workspace_id)
            identity = await client.identity()
            if identity.get("workspace_id") != workspace_id:
                fail("knowledge_workspace_mismatch", 403)
            reference = uuid4().hex
            old = self.store.binding()
            retained = list(
                dict.fromkeys(
                    [
                        *(old.get("retained_credentials", []) if old else []),
                        *([old["credential_ref"]] if old else []),
                    ]
                )
            )
            new_binding = {
                "origin": self.origin,
                "user_id": identity["user_id"],
                "workspace_id": workspace_id,
                "credential_ref": reference,
                "retained_credentials": retained,
            }
            backend = self._credentials()
            try:
                backend.set_password(self.namespace, reference, token)
                if backend.get_password(self.namespace, reference) != token:
                    fail("knowledge_credentials_unavailable", 503)
                self.store.save_binding(new_binding)
            except StoreError:
                try:
                    backend.delete_password(self.namespace, reference)
                except Exception:  # noqa: BLE001 - preserve an explicit recovery state.
                    fail("knowledge_binding_recovery_required", 503)
                raise
            except Exception:  # noqa: BLE001 - never include keychain messages or secrets.
                try:
                    backend.delete_password(self.namespace, reference)
                except Exception:  # noqa: BLE001
                    fail("knowledge_binding_recovery_required", 503)
                fail("knowledge_binding_failed", 503)
            # Successful replacement invalidates the prior credential slot; failures remain visible.
            remaining = []
            for old_ref in retained:
                try:
                    if backend.get_password(self.namespace, old_ref) is not None:
                        backend.delete_password(self.namespace, old_ref)
                except Exception:  # noqa: BLE001
                    log.warning("knowledge_previous_credential_retained")
                    remaining.append(old_ref)
            if remaining != retained:
                self.store.save_binding({**new_binding, "retained_credentials": remaining})
            log.info("knowledge_user_bound")
            return self.status()

    @bounded
    async def bases(self):
        client, _ = await self._authorized()
        return {"items": await client.knowledge_bases()}

    def _scope(self, identifier, binding):
        scope = self.store.read("scopes", identifier)
        if any(scope.get(key) != binding[key] for key in ("user_id", "workspace_id", "origin")):
            fail("knowledge_scope_identity_mismatch", 403)
        return scope

    @bounded
    async def create_scope(self, body):
        if body.confirm_source_times is not True:
            fail("knowledge_source_approval_required", 403)
        cutoff = timestamp(body.cutoff)
        if len({row.document_id for row in body.documents}) != len(body.documents):
            fail("knowledge_duplicate_document", 422)
        # Reject future/unknown material before any remote retrieval or embedding request.
        if any(timestamp(row.available_at) > cutoff for row in body.documents):
            fail("knowledge_source_after_cutoff", 422)
        async with self.lock:
            client, binding = await self._authorized()
            documents = []
            for approval in body.documents:
                meta = await client.document(approval.document_id)
                self._ready(meta)
                raw = await client.original(approval.document_id)
                chunks = await client.chunks(approval.document_id)
                documents.append(
                    {
                        "document_id": approval.document_id,
                        "kb_id": meta["kb_id"],
                        "title": meta["title"],
                        "sha256": digest(raw),
                        "chunks_sha256": chunk_fingerprint(chunks),
                        "available_at": approval.available_at,
                        "time_evidence": approval.time_evidence,
                    }
                )
            await self._still_authorized(binding)
            return self.store.create(
                "scopes",
                {
                    "origin": self.origin,
                    "user_id": binding["user_id"],
                    "workspace_id": binding["workspace_id"],
                    "report_period": body.report_period,
                    "cutoff": body.cutoff,
                    "documents": documents,
                    "time_approval": "authenticated_user",
                },
            )

    @staticmethod
    def _ready(meta):
        if meta.get("parse_status") != "completed" or meta.get("enable_status") != "enabled":
            fail("knowledge_document_not_ready", 409)

    async def _verify_document(self, client, row):
        raw = await client.original(row["document_id"])
        chunks = await client.chunks(row["document_id"])
        if digest(raw) != row["sha256"]:
            fail("knowledge_original_changed")
        if chunk_fingerprint(chunks) != row["chunks_sha256"]:
            fail("knowledge_chunks_changed")
        return raw, chunks

    @bounded
    async def search(self, body):
        client, binding = await self._authorized()
        ids = body.document_ids
        bases = body.knowledge_base_ids
        scope = self._scope(body.scope_id, binding) if body.scope_id else None
        if scope:
            allowed = {row["document_id"]: row for row in scope["documents"]}
            if ids is not None and not set(ids) <= set(allowed):
                fail("knowledge_document_outside_scope", 403)
            ids = list(allowed) if ids is None else ids
            if not set(bases) <= {row["kb_id"] for row in allowed.values()}:
                fail("knowledge_library_outside_scope", 403)
            # Recheck original bytes prior to admitting any hits from the frozen corpus.
            approved_chunks = {}
            for identifier in ids:
                _, chunks = await self._verify_document(client, allowed[identifier])
                approved_chunks.update({chunk["chunk_id"]: chunk for chunk in chunks})
        hits = await client.search(body.query, bases, ids, limit=8)
        if scope and any(
            hit["document_id"] not in ids or hit["kb_id"] != allowed[hit["document_id"]]["kb_id"]
            for hit in hits
        ):
            fail("knowledge_upstream_scope_violation", 502)
        if scope:
            for hit in hits:
                original = approved_chunks.get(hit["chunk_id"])
                if (
                    original is None
                    or hit["document_id"] != original["document_id"]
                    or not hit["content"]
                    or hit["content"] not in original["content"]
                ):
                    fail("knowledge_chunks_changed")
        await self._still_authorized(binding)
        return {"items": hits, "scope_id": body.scope_id, "generated_answer": False}

    @bounded
    async def read(self, body):
        client, binding = await self._authorized()
        if body.scope_id:
            scope = self._scope(body.scope_id, binding)
            row = next(
                (row for row in scope["documents"] if row["document_id"] == body.document_id), None
            )
            if not row:
                fail("knowledge_document_outside_scope", 403)
            _, approved_chunks = await self._verify_document(client, row)
        meta = await client.document(body.document_id)
        self._ready(meta)
        chunks = approved_chunks if body.scope_id else await client.chunks(body.document_id)
        await self._still_authorized(binding)
        return {"document": meta, "chunks": chunks}

    @bounded
    async def freeze(self, body):
        async with self.lock:
            client, binding = await self._authorized()
            scope = self._scope(body.scope_id, binding)
            allowed = {row["document_id"]: row for row in scope["documents"]}
            if not set(body.chunks) <= set(allowed):
                fail("knowledge_document_outside_scope", 403)
            documents, excerpts, files = [], [], {}
            for identifier, selection in sorted(body.chunks.items()):
                if not selection or len(selection) > 20 or len(set(selection)) != len(selection):
                    fail("knowledge_chunk_selection_invalid", 422)
                row = allowed[identifier]
                raw, current_chunks = await self._verify_document(client, row)
                chunks = {item["chunk_id"]: item for item in current_chunks}
                if not set(selection) <= set(chunks):
                    fail("knowledge_chunk_not_found", 404)
                if digest(await client.original(identifier)) != row["sha256"]:
                    fail("knowledge_original_changed")
                files[row["sha256"] + ".bin"] = raw
                documents.append(row)
                for key in selection:
                    chunk = chunks[key]
                    if chunk["document_id"] != identifier or chunk["kb_id"] != row["kb_id"]:
                        fail("knowledge_upstream_scope_violation", 502)
                    excerpts.append(
                        {
                            **chunk,
                            "content_sha256": digest(chunk["content"].encode()),
                            "original_sha256": row["sha256"],
                        }
                    )
            await self._still_authorized(binding)
            return self.store.create(
                "evidence",
                {
                    "scope_id": body.scope_id,
                    "report_period": scope["report_period"],
                    "cutoff": scope["cutoff"],
                    "workspace_id": binding["workspace_id"],
                    "user_id": binding["user_id"],
                    "documents": documents,
                    "excerpts": excerpts,
                    "formal_report_status": "NOT_ACCEPTED",
                },
                files,
            )
