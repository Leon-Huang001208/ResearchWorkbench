"""Session-bound current research receipts; model text cannot select a library."""

from __future__ import annotations

import hashlib
import math
from collections import deque

from ..store import StoreError
from .storage import canonical, digest, fail


class CurrentResearch:
    def _session(self, sid, *, formal=False):
        row = self.owner_store.session(sid)
        if row.get("created") is not True:
            fail("knowledge_session_unconfirmed", 403)
        if "uploads" not in row.get("source_scope", ["datahub", "web", "uploads"]):
            fail("research_source_excluded", 403)
        if row.get("knowledge_single_turn") and not formal:
            fail("knowledge_run_not_authorized", 403)
        return row

    async def _formal_grant(self, sid, host, caller_session_id):
        caller = self.owner_store.data["sessions"].get(caller_session_id, {})
        if caller.get("knowledge_single_turn") and caller_session_id != sid:
            fail("knowledge_run_not_authorized", 403)
        if not self.owner_store.session(sid).get("knowledge_single_turn"):
            return None
        self._session(sid, formal=True)
        # The private Native bridge supplies caller identity, not model arguments.
        if (
            host is None
            or host.store is not self.owner_store
            or host.knowledge is not self
            or caller_session_id != sid
        ):
            fail("knowledge_run_not_authorized", 403)
        from .routes import grant_snapshot

        grant = grant_snapshot(host, sid)
        await self._formal_check(sid, grant, host)
        return grant

    async def _formal_check(self, sid, grant, host):
        from .routes import active_scope, grant_snapshot

        self._session(sid, formal=True)
        if await active_scope(host, sid) != grant[0] or grant_snapshot(host, sid) != grant:
            fail("knowledge_run_not_authorized", 403)

    async def _formal_query(self, body, grant, host):
        from .models import Search

        async with self.lock:
            scope = await self.research_scope(grant[0])
            result = await self.search(
                Search(
                    query=body.query,
                    knowledge_base_ids=sorted({row["kb_id"] for row in scope["documents"]}),
                    scope_id=grant[0],
                ),
                canonical_hits=True,
            )
            client, binding = await self._authorized()
            allowed = {row["document_id"]: row for row in scope["documents"]}
            prepared, seen = [], set()
            for chunk in result["items"]:
                key = chunk["document_id"], chunk["chunk_id"]
                if key in seen:
                    continue
                seen.add(key)
                source = allowed.get(chunk["document_id"])
                if source is None or chunk["kb_id"] != source["kb_id"]:
                    fail("knowledge_upstream_scope_violation", 502)
                meta = await client.document(source["document_id"])
                self._ready(meta)
                if meta["kb_id"] != source["kb_id"]:
                    fail("knowledge_upstream_scope_violation", 502)
                _, chunks = await self._verify_document(client, source)
                current = next(
                    (row for row in chunks if row["chunk_id"] == chunk["chunk_id"]), None
                )
                if current != chunk:
                    fail("knowledge_chunks_changed")
                if len(chunk["content"]) > 16000:
                    fail("knowledge_current_chunk_budget", 413)
                prepared.append(
                    {
                        "session_id": body.session_id,
                        **{key: binding[key] for key in ("origin", "user_id", "workspace_id")},
                        "purpose": "approved_research_scope",
                        "knowledge_scope_id": grant[0],
                        "native_grant": list(grant),
                        "kb_id": source["kb_id"],
                        "document_id": source["document_id"],
                        # This versions the immutable approved snapshot, not the sync manifest.
                        "document_version": 1,
                        "sha256": source["sha256"],
                        "chunks_sha256": source["chunks_sha256"],
                        "title": source["title"],
                        "chunk": chunk,
                        "chunk_sha256": digest(canonical(chunk)),
                        "available_at": source["available_at"],
                        "time_evidence": source["time_evidence"],
                        "historical_eligible": False,
                    }
                )
            await self._still_authorized(binding)
            await self.research_scope(grant[0])
            # This is the last await before publishing session-bound receipts.
            await self._formal_check(body.session_id, grant, host)
            receipts = [self.store.create("receipts", payload) for payload in prepared]
            return {
                "items": [self._projection(row) for row in receipts],
                "session_id": body.session_id,
                "generated_answer": False,
            }

    async def _formal_read(self, body, grant, host):
        client, binding = await self._authorized()
        row = self.store.read("receipts", body.hit_id)
        if row.get("session_id") != body.session_id:
            fail("knowledge_hit_session_mismatch", 403)
        if (
            row.get("purpose") != "approved_research_scope"
            or row.get("knowledge_scope_id") != grant[0]
            or tuple(row.get("native_grant", [])) != grant
            or any(row.get(key) != binding[key] for key in ("origin", "user_id", "workspace_id"))
        ):
            fail("knowledge_hit_identity_mismatch", 403)
        scope = await self.research_scope(grant[0])
        source = next(
            (item for item in scope["documents"] if item["document_id"] == row["document_id"]),
            None,
        )
        if source is None or any(
            row[key] != source[key] for key in ("kb_id", "sha256", "chunks_sha256")
        ):
            fail("knowledge_hit_identity_mismatch", 403)
        _, chunks = await self._verify_document(client, source)
        if not any(chunk == row["chunk"] for chunk in chunks):
            fail("knowledge_chunks_changed")
        await self._still_authorized(binding)
        await self.research_scope(grant[0])
        await self._formal_check(body.session_id, grant, host)
        if self.store.binding() != binding:
            fail("knowledge_binding_changed", 409)
        return self._projection(row, content=True)

    async def _current_authorized(self, sid):
        self._session(sid)
        client, binding = await self._authorized()
        state = self.sync.status()
        if not state.get("configured") or not self.sync.matches_binding(binding):
            fail("knowledge_sync_binding_required", 409)
        kb_id = state["knowledge_base_id"]
        if kb_id not in {item["id"] for item in await client.knowledge_bases()}:
            fail("knowledge_library_access_revoked", 403)
        return client, binding, kb_id

    def _receipt(self, sid, hit_id, binding, kb_id):
        row = self.store.read("receipts", hit_id)
        if row.get("session_id") != sid:
            fail("knowledge_hit_session_mismatch", 403)
        if row.get("kb_id") != kb_id or any(
            row.get(key) != binding[key] for key in ("origin", "user_id", "workspace_id")
        ):
            fail("knowledge_hit_identity_mismatch", 403)
        return row

    def _current_config(self, binding, kb_id, rows=None):
        def published(values):
            keys = ("document_id", "kb_id", "sha256", "version", "path")
            return sorted(tuple(row[key] for key in keys) for row in values)

        if (
            not self.sync.matches_binding(binding)
            or self.sync.status().get("knowledge_base_id") != kb_id
            or (rows is not None and published(self.sync.current_documents()) != published(rows))
        ):
            fail("knowledge_current_version_changed")

    @staticmethod
    def _projection(row, *, source_status="current", content=False):
        chunk = row["chunk"]
        value = {
            "session_id": row["session_id"],
            "hit_id": row["id"],
            "source_id": "knowledge:" + row["id"],
            "title": row["title"],
            "snippet": chunk["content"],
            "locator": {key: chunk[key] for key in ("chunk_index", "start_at", "end_at")},
            "sha256": row["sha256"],
            "document_version": row["document_version"],
            "source_status": source_status,
            "historical_eligible": False,
            "limitations": [
                "source_time_unknown",
                *(["source_" + source_status] if source_status != "current" else []),
            ],
        }
        if content:
            value["content"] = chunk["content"]
        return value

    async def _current_query(self, body):
        from .service import chunk_fingerprint

        async with self.lock:
            client, binding, kb_id = await self._current_authorized(body.session_id)
            if not self.sync.status().get("enabled"):
                fail("knowledge_sync_disabled", 409)
            rows = self.sync.current_documents()
            allowed = {}
            for row in rows:
                previous = allowed.get(row["document_id"])
                if row["kb_id"] != kb_id or (previous and previous["sha256"] != row["sha256"]):
                    fail("knowledge_sync_manifest_invalid")
                # Identical copies and renames can share one verified upstream document.
                allowed.setdefault(row["document_id"], row)
            # Top8 per disjoint batch is sufficient to compute the global Top8.
            candidates = []
            identifiers = sorted(allowed)
            for offset in range(0, len(identifiers), 128):
                batch = identifiers[offset : offset + 128]
                hits = await client.search(body.query, [kb_id], batch, limit=8)
                for hit in hits:
                    if hit["document_id"] not in batch or hit["kb_id"] != kb_id:
                        fail("knowledge_upstream_scope_violation", 502)
                    score = hit.get("score", 0)
                    if (
                        isinstance(score, bool)
                        or not isinstance(score, (int, float))
                        or not math.isfinite(score)
                    ):
                        fail("knowledge_upstream_score_invalid", 502)
                    candidates.append(hit)
                candidates.sort(key=lambda hit: hit.get("score", 0), reverse=True)
                candidates = candidates[:8]
            selected, seen = [], set()
            for hit in candidates:
                key = hit["document_id"], hit["chunk_id"]
                if key not in seen:
                    seen.add(key)
                    selected.append(hit)
                if len(selected) == 8:
                    break
            prepared, documents, originals, byte_count = [], {}, {}, 0
            for hit in selected:
                identifier = hit["document_id"]
                row = allowed[identifier]
                if identifier not in documents:
                    meta = await client.document(identifier)
                    self._ready(meta)
                    if meta["kb_id"] != kb_id:
                        fail("knowledge_upstream_scope_violation", 502)
                    raw, chunks = await client.original(identifier), await client.chunks(identifier)
                    byte_count += len(raw)
                    # Top8 may contain eight distinct 8 MiB originals. Raw storage is
                    # bounded here independently of the total library/history size.
                    if len(raw) > 8 * 1024 * 1024 or byte_count > 64 * 1024 * 1024:
                        fail("knowledge_current_query_budget", 413)
                    if digest(raw) != row["sha256"]:
                        fail("knowledge_current_version_changed", 409)
                    fingerprint = chunk_fingerprint(chunks)
                    if digest(await client.original(identifier)) != row["sha256"]:
                        fail("knowledge_current_version_changed", 409)
                    originals.setdefault(row["sha256"], raw)
                    documents[identifier] = chunks, fingerprint, meta
                chunks, fingerprint, meta = documents[identifier]
                chunk = next(
                    (chunk for chunk in chunks if chunk["chunk_id"] == hit["chunk_id"]), None
                )
                if (
                    chunk is None
                    or chunk["document_id"] != identifier
                    or chunk["kb_id"] != kb_id
                    or not hit["content"]
                    or hit["content"] not in chunk["content"]
                ):
                    fail("knowledge_chunks_changed")
                if len(chunk["content"]) > 16000:
                    fail("knowledge_current_chunk_budget", 413)
                prepared.append(
                    {
                        "session_id": body.session_id,
                        "origin": binding["origin"],
                        "user_id": binding["user_id"],
                        "workspace_id": binding["workspace_id"],
                        "kb_id": kb_id,
                        "document_id": identifier,
                        "document_version": row["version"],
                        "sha256": row["sha256"],
                        "chunks_sha256": fingerprint,
                        "path": row["path"],
                        "title": meta["title"],
                        "chunk": chunk,
                        "chunk_sha256": digest(canonical(chunk)),
                        "historical_eligible": False,
                        "available_at": None,
                        "time_evidence": None,
                    }
                )
            await self._still_authorized(binding)
            self._session(body.session_id)
            self._current_config(binding, kb_id, rows)
            # Permission is rechecked after IO and before publishing any receipt.
            if kb_id not in {item["id"] for item in await client.knowledge_bases()}:
                fail("knowledge_library_access_revoked", 403)
            self._current_config(binding, kb_id, rows)
            for sha, raw in originals.items():
                # Durable pins precede receipts: a published hit never depends on
                # a source file or a later WeKnora original download to freeze.
                self.sync.pin_snapshot(sha, raw)
            originals.clear()
            receipts = [self.store.create("receipts", payload) for payload in prepared]
            return {
                "items": [self._projection(row) for row in receipts],
                "session_id": body.session_id,
                "generated_answer": False,
            }

    async def _receipt_status(self, client, row):
        from .service import chunk_fingerprint

        try:
            meta = await client.document(row["document_id"])
            if meta["kb_id"] != row["kb_id"]:
                fail("knowledge_library_access_revoked", 403)
            if meta.get("parse_status") != "completed" or meta.get("enable_status") != "enabled":
                return "changed"
            raw = await client.original(row["document_id"])
            chunks = await client.chunks(row["document_id"])
            if digest(raw) != row["sha256"] or chunk_fingerprint(chunks) != row["chunks_sha256"]:
                return "changed"
        except StoreError as exc:
            if exc.code == "weknora_not_found" and exc.status == 404:
                return "deleted"
            raise
        if not any(
            item["document_id"] == row["document_id"] and item["sha256"] == row["sha256"]
            for item in self.sync.current_documents()
        ):
            return "superseded"
        return "current"

    async def _current_read(self, body):
        client, binding, kb_id = await self._current_authorized(body.session_id)
        row = self._receipt(body.session_id, body.hit_id, binding, kb_id)
        state = await self._receipt_status(client, row)
        await self._still_authorized(binding)
        if kb_id not in {item["id"] for item in await client.knowledge_bases()}:
            fail("knowledge_library_access_revoked", 403)
        self._current_config(binding, kb_id)
        self._session(body.session_id)
        return self._projection(row, source_status=state, content=True)

    async def _current_freeze(self, body):
        async with self.lock:
            client, binding, kb_id = await self._current_authorized(body.session_id)
            receipts = [self._receipt(body.session_id, key, binding, kb_id) for key in body.hit_ids]
            documents, excerpts, files = {}, [], {}
            for row in receipts:
                raw = self.sync.snapshot(row["sha256"])
                if digest(raw) != row["sha256"]:
                    fail("knowledge_evidence_integrity")
                state = await self._freeze_source_status(client, row, raw)
                files[row["sha256"] + ".bin"] = raw
                documents[(row["document_id"], row["sha256"])] = {
                    key: row[key]
                    for key in (
                        "document_id",
                        "kb_id",
                        "sha256",
                        "document_version",
                        "title",
                        "chunks_sha256",
                        "available_at",
                        "time_evidence",
                    )
                }
                excerpts.append(
                    {
                        **row["chunk"],
                        "hit_id": row["id"],
                        "original_sha256": row["sha256"],
                        "content_sha256": digest(row["chunk"]["content"].encode()),
                        "source_status": state,
                    }
                )
            await self._still_authorized(binding)
            if kb_id not in {item["id"] for item in await client.knowledge_bases()}:
                fail("knowledge_library_access_revoked", 403)
            self._current_config(binding, kb_id)
            self._session(body.session_id)
            return self.store.create(
                "evidence",
                {
                    "session_id": body.session_id,
                    "receipt_ids": body.hit_ids,
                    "purpose": "current_research",
                    "origin": binding["origin"],
                    "user_id": binding["user_id"],
                    "workspace_id": binding["workspace_id"],
                    "documents": list(documents.values()),
                    "excerpts": excerpts,
                    "historical_eligible": False,
                    "formal_report_status": "NOT_ACCEPTED",
                },
                files,
            )

    async def _freeze_source_status(self, client, row, raw):
        """Source observation is advisory; live identity and KB checks remain mandatory."""
        try:
            meta = await client.document(row["document_id"])
        except StoreError as exc:
            if exc.code == "weknora_not_found" and exc.status == 404:
                return "deleted"
            if exc.status in {502, 503, 504}:
                return "unavailable"
            raise
        if meta["kb_id"] != row["kb_id"]:
            fail("knowledge_library_access_revoked", 403)
        if (
            meta.get("parse_status") != "completed"
            or meta.get("enable_status") != "enabled"
            or (meta.get("file_hash") and meta["file_hash"] != hashlib.md5(raw).hexdigest())
        ):
            return "changed"
        return (
            "current"
            if any(
                item["document_id"] == row["document_id"] and item["sha256"] == row["sha256"]
                for item in self.sync.current_documents()
            )
            else "superseded"
        )

    def registered_sources(self, sid):
        session = self.owner_store.session(sid)
        if session.get("created") is not True or "uploads" not in session.get(
            "source_scope", ["datahub", "web", "uploads"]
        ):
            return []
        binding = self.store.binding()
        if not binding:
            return []
        formal = session.get("knowledge_single_turn") is True
        grant, approved = None, {}
        if formal:
            # Read-only result views keep the original scope/request binding even
            # after the Native turn ends; this does not authorize another tool call.
            receipt = self.owner_store.data["receipts"].get(
                f"{sid}:{session.get('delivery_key')}", {}
            )
            grant = (
                receipt.get("knowledge_scope_id"),
                receipt.get("delivery", {}).get("task_id"),
                receipt.get("knowledge_request_digest"),
                receipt.get("digest"),
            )
            if not all(grant):
                return []
            approved = {
                row["document_id"]: row for row in self._scope(grant[0], binding)["documents"]
            }
        elif not self.sync.matches_binding(binding):
            return []
        result = deque(maxlen=100)
        for row in self.store.records("receipts"):
            if row.get("session_id") != sid or any(
                row.get(key) != binding[key] for key in ("origin", "user_id", "workspace_id")
            ):
                continue
            if formal:
                source = approved.get(row.get("document_id"), {})
                if (
                    row.get("purpose") != "approved_research_scope"
                    or tuple(row.get("native_grant", [])) != grant
                    or row.get("knowledge_scope_id") != grant[0]
                    or any(
                        row.get(key) != source.get(key)
                        for key in ("kb_id", "sha256", "chunks_sha256")
                    )
                    or not source
                ):
                    continue
            elif row.get("purpose") == "approved_research_scope":
                continue
            result.append(
                {
                    "id": "knowledge:" + row["id"],
                    "source_id": "knowledge:" + row["id"],
                    "title": row["title"],
                    "content": row["chunk"]["content"],
                    "sha256": row["sha256"],
                    "digest_scope": "full_file",
                    "historical_eligible": False,
                    "admission": {"report_admitted": False},
                    "limitations": ["source_time_unknown"],
                }
            )
        return list(result)
