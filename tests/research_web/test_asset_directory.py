"""Account-scoped directory loading, authorization and bounded cache regressions."""

import asyncio
from types import SimpleNamespace

import pytest

from app.research_web.asset_directory import AssetDirectory


def directory_rows(count=6001):
    return [
        {
            "asset": f"{i:06}.SH",
            "code": f"{i:06}",
            "name": "贵州茅台" if i == 6000 else f"测试{i}",
            "exchange": "SH",
            "asset_type": "stock",
        }
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_directory_coalesces_cold_load_retains_over5000_and_ranks_pinyin(tmp_path):
    calls = []
    ready = asyncio.Event()

    async def loader():
        calls.append(1)
        await ready.wait()
        return {
            "items": directory_rows(),
            "total_count": 6001,
            "provider": "tinysoft",
            "as_of": "2026-10-22",
            "retrieved_at": "2026-10-22T00:00:00Z",
            "limitations": [],
        }

    index = AssetDirectory(tmp_path, loader=loader, fingerprint=lambda: "authorized-a")
    assert index.search("gzmt")["status"] == "loading"
    index.search("6000")
    await asyncio.sleep(0)
    assert len(calls) == 1 and index.active
    ready.set()
    await index.wait()
    result = index.search("gzmt")
    assert result["status"] == "ready" and result["total_count"] == 6001
    assert result["items"][0]["asset"] == "006000.SH"
    restored = AssetDirectory(tmp_path, loader=loader, fingerprint=lambda: "authorized-a")
    assert restored.search("006000")["items"][0]["name"] == "贵州茅台"
    assert len(calls) == 1
    await index.close()
    await restored.close()


@pytest.mark.asyncio
async def test_directory_stale_keeps_same_authorization_but_configuration_change_hides_old(
    tmp_path,
):
    clock = [0.0]
    revision = ["a"]
    fail = [False]

    async def loader():
        if fail[0]:
            raise ValueError("private upstream content")
        return {
            "items": directory_rows(2),
            "total_count": 2,
            "provider": "tinysoft",
            "limitations": [],
        }

    index = AssetDirectory(
        tmp_path, loader=loader, fingerprint=lambda: revision[0], clock=lambda: clock[0]
    )
    index.search("")
    await index.wait()
    clock[0] = 86401
    fail[0] = True
    stale = index.search("")
    assert stale["status"] == "stale" and len(stale["items"]) == 2
    await index.wait()
    assert index.search("")["failure_code"] == "asset_directory_load_failed"
    revision[0] = "b"
    assert index.search("")["items"] == []
    await index.close()


@pytest.mark.asyncio
async def test_directory_denied_authorization_never_returns_cache_or_starts_loader(tmp_path):
    calls = []

    async def loader():
        calls.append(1)
        return {"items": directory_rows(1), "total_count": 1}

    def denied():
        raise ValueError("private credential diagnostic")

    index = AssetDirectory(tmp_path, loader=loader, fingerprint=denied)
    result = index.search("贵州茅台")
    assert result["status"] == "unavailable" and result["items"] == []
    assert result["failure_code"] == "asset_directory_unauthorized" and calls == []
    await index.close()


@pytest.mark.asyncio
async def test_directory_close_waits_real_loader_and_remains_active(tmp_path):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def loader():
        entered.set()
        await release.wait()
        return {"items": directory_rows(1), "total_count": 1}

    index = AssetDirectory(tmp_path, loader=loader, fingerprint=lambda: "a")
    index.search("")
    await entered.wait()
    closing = asyncio.create_task(index.close())
    await asyncio.sleep(0)
    assert not closing.done() and index.active
    release.set()
    await closing
    assert not index.active


@pytest.mark.asyncio
async def test_datahub_directory_uses_account_secret_and_checks_before_and_after_await(monkeypatch):
    from app.research_web.datahub import DataHub, providers_cjpy
    from app.research_web.store import StoreError

    hub = object.__new__(DataHub)
    hub.directory_tasks = set()
    revision = ["a"]
    reads = []
    fetched = []
    hub.directory_fingerprint = lambda: revision[0]
    hub.connections = SimpleNamespace(
        read_source_secret=lambda source: reads.append(source) or "fake-account-token"
    )

    async def fetch_directory(*, token):
        fetched.append(token)
        revision[0] = "b"
        return {"items": directory_rows(1), "total_count": 1}

    monkeypatch.setattr(providers_cjpy, "fetch_directory", fetch_directory, raising=False)
    with pytest.raises(StoreError, match="配置已变化"):
        await hub.asset_directory()
    assert reads == ["tinysoft"] and fetched == ["fake-account-token"]
    assert hub.directory_tasks == set()


def test_datahub_directory_fingerprint_resolves_only_explicit_tinysoft(monkeypatch):
    import app.research_web.datahub as module
    from app.research_web.datahub import DataHub

    seen = []
    hub = object.__new__(DataHub)
    hub.closed = False
    hub._latest_probes = dict
    hub.connections = SimpleNamespace(statuses=lambda: {"tinysoft": {"configured": True}})
    hub.source_configuration_digest = lambda source: f"account-specific-{source}"
    monkeypatch.setattr(
        module,
        "resolve",
        lambda query, **kwargs: seen.append(query) or SimpleNamespace(provider_id="tinysoft"),
    )
    assert hub.directory_fingerprint() == "account-specific-tinysoft"
    assert seen[0].capability == "search_assets" and seen[0].source == "tinysoft"
    assert seen[0].allow_fallback is False


@pytest.mark.asyncio
async def test_datahub_directory_configuration_changed_during_secret_read_never_fetches(
    monkeypatch,
):
    from app.research_web.datahub import DataHub, providers_cjpy
    from app.research_web.store import StoreError

    hub = object.__new__(DataHub)
    hub.directory_tasks = set()
    revision = ["a"]
    fetched = []
    hub.directory_fingerprint = lambda: revision[0]

    def read_secret(source):
        revision[0] = "b"
        return "fake-private-token"

    async def fetch_directory(**kwargs):
        fetched.append(1)
        return {}

    hub.connections = SimpleNamespace(read_source_secret=read_secret)
    monkeypatch.setattr(providers_cjpy, "fetch_directory", fetch_directory, raising=False)
    with pytest.raises(StoreError, match="配置已变化"):
        await hub.asset_directory()
    assert fetched == [] and hub.directory_tasks == set()


@pytest.mark.asyncio
async def test_incomplete_or_oversized_directory_never_replaces_a_valid_cache(tmp_path):
    clock = [0.0]
    value = [{"items": directory_rows(1), "total_count": 1}]

    async def loader():
        return value[0]

    index = AssetDirectory(tmp_path, loader=loader, fingerprint=lambda: "a", clock=lambda: clock[0])
    index.search("")
    await index.wait()
    for replacement in [
        {"items": directory_rows(2), "total_count": 3},
        {"items": directory_rows(20001), "total_count": 20001},
    ]:
        clock[0] += 86401
        value[0] = replacement
        index.search("")
        await index.wait()
        result = index.search("")
        assert result["total_count"] == 1 and result["status"] == "stale"
        assert result["failure_code"] == "asset_directory_load_failed"
    await index.close()


@pytest.mark.asyncio
async def test_untrusted_cache_shape_is_rejected_without_breaking_search(tmp_path):
    parent = tmp_path / "asset-directory"
    parent.mkdir()
    (parent / "index.json").write_text("[]")

    async def loader():
        return {"items": directory_rows(1), "total_count": 1}

    index = AssetDirectory(tmp_path, loader=loader, fingerprint=lambda: "a")
    assert index.search("")["status"] == "loading"
    await index.wait()
    assert index.search("")["status"] == "ready"
    await index.close()


@pytest.mark.asyncio
async def test_unknown_pending_is_never_removed_and_old_cache_stays_readable(tmp_path):
    clock = [0.0]

    async def loader():
        return {"items": directory_rows(1), "total_count": 1}

    index = AssetDirectory(tmp_path, loader=loader, fingerprint=lambda: "a", clock=lambda: clock[0])
    index.search("")
    await index.wait()
    pending = tmp_path / "asset-directory" / ".pending.json"
    pending.write_bytes(b"unknown prior transaction")
    clock[0] = 86401
    assert index.search("")["status"] == "stale"
    await index.wait()
    result = index.search("")
    assert result["status"] == "stale" and result["total_count"] == 1
    assert result["failure_code"] == "asset_directory_load_failed"
    assert pending.read_bytes() == b"unknown prior transaction"
    assert len(list(pending.parent.iterdir())) == 2
    await index.close()


@pytest.mark.asyncio
async def test_directory_rejects_symlink_cache_and_revalidates_auth_after_await(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "asset-directory").symlink_to(outside, target_is_directory=True)
    revision = ["a"]

    async def loader():
        revision[0] = "b"
        return {"items": directory_rows(1), "total_count": 1, "provider": "tinysoft"}

    index = AssetDirectory(tmp_path, loader=loader, fingerprint=lambda: revision[0])
    index.search("")
    await index.wait()
    assert index.search("")["items"] == []
    assert not list(outside.iterdir())
    await index.close()
