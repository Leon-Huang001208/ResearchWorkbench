import json

import pytest

from app.research_web.tabbit import TabbitError, TabbitIntegration
from app.research_web.store import Store


class TabbitRuntimeFixture:
    def __init__(self):
        self.calls = []
        self.tabs = [
            {
                "tabId": 7,
                "windowId": 1,
                "index": 0,
                "title": "Research",
                "url": "https://example.com/research",
                "active": True,
                "state": "available",
            },
            {
                "tabId": 8,
                "windowId": 1,
                "index": 1,
                "title": "Internal",
                "url": "chrome://settings",
                "active": False,
                "state": "available",
            },
            {
                "tabId": 9,
                "windowId": 1,
                "index": 2,
                "title": "Busy",
                "url": "https://example.com/busy",
                "active": False,
                "state": "busy",
            },
        ]

    async def plugin_json(self, method, path, *, params=None, payload=None):
        self.calls.append((method, path, params, payload))
        if path == "/research/tabbit/status":
            return {
                "status": "ready",
                "pluginVersion": "0.3.4",
                "browserVersion": "1.13.23",
                "launcherPresent": True,
                "onlineInstances": 1,
                "selectedInstance": "ABCDEF0123456789",
            }
        if path == "/research/tabbit/access":
            return {"accepted": True}
        if path == "/research/tabbit/tabs":
            return {"tabs": self.tabs}
        if path == "/research/tabbit/live-extract":
            return {
                "markers": [
                    {
                        "tabId": tab_id,
                        "title": "Research",
                        "marker": f"@[Research](rwb-tabbit:{tab_id}-token)",
                    }
                    for tab_id in payload["tabIds"]
                ]
            }
        raise AssertionError(path)


@pytest.fixture
def integration(tmp_path):
    runtime = TabbitRuntimeFixture()
    store = Store(tmp_path)
    sid = store.create("fingpt", "Tabbit test")["id"]
    return TabbitIntegration(runtime, store), runtime, sid


@pytest.mark.asyncio
async def test_tabbit_defaults_are_browser_on_fetch_off_and_status_is_safe(integration):
    tabbit, _, _ = integration

    status = await tabbit.status()

    assert status == {
        "browser_enabled": True,
        "web_fetch_enabled": False,
        "instance_id": None,
        "restart_required": False,
        "status": "ready",
        "plugin_version": "0.3.4",
        "browser_version": "1.13.23",
        "launcher_present": True,
        "cli_available": True,
        "online_instances": 1,
        "selected_instance": "ABCDEF0123456789",
        "instances": [],
    }
    assert "url" not in json.dumps(status).lower()


def test_tabbit_configuration_is_persisted_without_secrets(integration):
    tabbit, _, _ = integration

    result = tabbit.configure(
        browser_enabled=True,
        web_fetch_enabled=True,
        instance_id="ABCDEF0123456789",
    )

    assert result["restart_required"] is True
    assert tabbit.config_path.stat().st_mode & 0o077 == 0
    assert json.loads(tabbit.config_path.read_text()) == {
        "browser_enabled": True,
        "web_fetch_enabled": True,
        "instance_id": "ABCDEF0123456789",
    }


def test_tabbit_configuration_rejects_fetch_without_browser_and_bad_instance(integration):
    tabbit, _, _ = integration
    with pytest.raises(TabbitError, match="浏览器自动化"):
        tabbit.configure(browser_enabled=False, web_fetch_enabled=True, instance_id=None)
    with pytest.raises(TabbitError, match="实例"):
        tabbit.configure(browser_enabled=True, web_fetch_enabled=False, instance_id="not-an-id")


@pytest.mark.asyncio
async def test_tab_listing_requires_session_grant_and_filters_unclaimable_pages(integration):
    tabbit, runtime, sid = integration
    with pytest.raises(TabbitError) as denied:
        await tabbit.tabs(sid, query="", limit=50)
    assert denied.value.code == "tabbit_page_access_required"

    await tabbit.access(sid, "approve")
    result = await tabbit.tabs(sid, query="research", limit=50)

    assert result == {
        "items": [
            {
                "tab_id": 7,
                "instance_id": "ABCDEF0123456789",
                "title": "Research",
                "url": "https://example.com/research",
                "active": True,
            }
        ],
        "count": 1,
    }
    assert runtime.calls[-1][1] == "/research/tabbit/tabs"


@pytest.mark.asyncio
async def test_live_revalidation_finds_selected_tabs_beyond_public_candidate_limit(integration):
    tabbit, runtime, sid = integration
    runtime.tabs = [
        {
            "tabId": index,
            "url": f"https://example.com/{index}",
            "title": f"Page {index}",
            "active": False,
            "state": "available",
        }
        for index in range(1, 53)
    ]
    await tabbit.access(sid, "approve")

    markers = await tabbit.live_markers(
        sid,
        "abcdefgh",
        [{"tab_id": 52, "instance_id": "ABCDEF0123456789"}],
        confirmed=True,
    )

    assert markers == ["@[Research](rwb-tabbit:52-token)"]


@pytest.mark.asyncio
async def test_live_mentions_revalidate_tabs_and_preserve_order(integration):
    tabbit, runtime, sid = integration
    await tabbit.access(sid, "approve")

    markers = await tabbit.live_markers(
        sid,
        "abcdefgh1234",
        [
            {"tab_id": 7, "instance_id": "ABCDEF0123456789"},
        ],
        confirmed=True,
    )

    assert markers == ["@[Research](rwb-tabbit:7-token)"]
    assert runtime.calls[-1][3] == {
        "sessionId": sid,
        "requestId": "abcdefgh1234",
        "instanceId": "ABCDEF0123456789",
        "tabIds": [7],
    }


@pytest.mark.asyncio
async def test_live_mentions_fail_closed_for_missing_confirmation_duplicate_or_stale_tab(integration):
    tabbit, _, sid = integration
    await tabbit.access(sid, "approve")
    refs = [{"tab_id": 7, "instance_id": "ABCDEF0123456789"}]

    with pytest.raises(TabbitError) as confirmation:
        await tabbit.live_markers(sid, "abcdefgh", refs, confirmed=False)
    assert confirmation.value.code == "tabbit_claim_confirmation_required"

    with pytest.raises(TabbitError) as duplicate:
        await tabbit.live_markers(sid, "abcdefgh", refs * 2, confirmed=True)
    assert duplicate.value.code == "tabbit_duplicate_tab"

    with pytest.raises(TabbitError) as stale:
        await tabbit.live_markers(
            sid,
            "abcdefgh",
            [{"tab_id": 99, "instance_id": "ABCDEF0123456789"}],
            confirmed=True,
        )
    assert stale.value.code == "tabbit_tab_unavailable"
