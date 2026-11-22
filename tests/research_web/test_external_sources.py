import asyncio
import json

import httpx
import pytest

from app.research_web.datahub.broker import resolve
from app.research_web.datahub.catalog import build_catalog
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.external_sources import EXTERNAL_SOURCES, inventory_rows
from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_external import arguments, endpoint_request, fetch


def query(source="ext_fred", dataset="series", **params):
    return BusinessQuery(
        capability="external_data",
        source=source,
        parameters={
            "dataset": dataset,
            "arguments_json": json.dumps(params or {"params": {"series": "DFF"}}),
        },
    )


def test_inventory_preserves_all_sources_and_reference_boundary():
    assert len(EXTERNAL_SOURCES) == 41
    assert len(inventory_rows()) == 51
    assert len([row for row in inventory_rows() if row["status"] == "reference_only"]) == 10
    catalog = build_catalog(environ={}, connection_statuses={})
    by_id = {source["id"]: source for source in catalog["sources"]}
    assert not by_id["ext_morningstar"]["readiness"]["callable"]
    assert not by_id["ext_daole"]["readiness"]["callable"]
    assert by_id["ext_fred"]["readiness"]["health"] == "untested"
    assert resolve(BusinessQuery(capability="external_data")).provider_id == "ext_registry"


@pytest.mark.parametrize(
    "value",
    [
        "[]",
        "{",
        '{"url":"https://evil.test"}',
        '{"query":{"api_key":"x"}}',
        '{"body":{"registrationkey":"synthetic-bls-secret"}}',
        '{"body":{"nested":{"callback":"x"}}}',
    ],
)
def test_credentials_and_destinations_are_never_model_arguments(value):
    with pytest.raises(ProviderError):
        arguments(value)


@pytest.mark.parametrize("value", ["../secret", "%2e%2e", ".", "a/b"])
def test_path_parameters_cannot_change_registered_endpoint(value):
    with pytest.raises(ProviderError):
        endpoint_request("ext_daole", "data", {"params": {"dataset": value}})


@pytest.mark.asyncio
async def test_source_catalog_is_offline_and_does_not_fetch_credentials():
    async def reject(_request):
        raise AssertionError("catalog must be offline")

    result = await fetch(query("ext_registry", "catalog"), transport=httpx.MockTransport(reject))
    assert result.status == "snapshot"
    assert len(result.rows) == 51


@pytest.mark.asyncio
async def test_fred_csv_keeps_observation_dates_and_missing_values():
    async def reply(request):
        assert request.url.host == "fred.stlouisfed.org"
        assert request.url.params["id"] == "DFF"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            text="observation_date,DFF\n2026-10-01,3.64\n2026-10-02,.\n",
            headers={"content-type": "text/csv"},
        )

    result = await fetch(query(), transport=httpx.MockTransport(reply))
    assert result.status == "snapshot"
    assert result.rows == [
        {"observation_date": "2026-10-01", "DFF": "3.64"},
        {"observation_date": "2026-10-02", "DFF": "."},
    ]
    assert not result.pagination_complete


@pytest.mark.asyncio
async def test_redirect_and_http_200_vendor_errors_are_not_success():
    for response, reason in [
        (httpx.Response(302, headers={"location": "https://evil.test/"}), "redirect_denied"),
        (
            httpx.Response(200, json={"errorcode": -1, "errmsg": "private supplier detail"}),
            "vendor_rejected",
        ),
    ]:
        result = await fetch(
            query(), transport=httpx.MockTransport(lambda req, response=response: response)
        )
        assert result.status == "failed"
        assert result.rows == [] and result.raw == []
        assert result.limitations == [reason]


@pytest.mark.asyncio
async def test_cancel_interrupts_network_and_never_publishes_a_snapshot():
    entered = asyncio.Event()

    async def reply(_request):
        entered.set()
        await asyncio.Future()

    task = asyncio.create_task(fetch(query(), transport=httpx.MockTransport(reply)))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_authenticated_responses_cannot_reflect_credentials():
    class Secrets:
        def read_source_secret(self, source):
            assert source == "ext_tikhub"
            return "private-test-credential"

    async def reply(request):
        assert request.headers["authorization"] == "Bearer private-test-credential"
        return httpx.Response(200, json={"data": "private-test-credential"})

    result = await fetch(
        query("ext_tikhub", "douyin", params={}),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert result.status == "failed" and result.limitations == ["credential_reflection"]
    assert not result.raw and not result.rows


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401])
async def test_ths_existing_access_is_used_without_exchange_or_retry(status):
    class Secrets:
        def read_source_secret(self, _source):
            return json.dumps(
                {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"}
            )

    calls = []

    def reply(request):
        calls.append(request)
        assert request.url.path.endswith("real_time_quotation")
        assert request.headers["access_token"] == "synthetic-access"
        assert "refresh_token" not in request.headers
        return httpx.Response(status, json={"errorcode": 0, "tables": [{"latest": 4000}]})

    result = await fetch(
        query("ext_ths", "real_time_quotation", body={}),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert len(calls) == 1
    assert result.status == ("snapshot" if status == 200 else "failed")


@pytest.mark.asyncio
async def test_ths_refresh_response_never_becomes_research_data():
    class Secrets:
        def read_source_secret(self, _source):
            return json.dumps({"refresh_token": "refresh-test-secret"})

    async def reply(request):
        if request.url.path.endswith("get_access_token"):
            assert request.headers["refresh_token"] == "refresh-test-secret"
            return httpx.Response(
                200, json={"errorcode": 0, "data": {"access_token": "short-lived-secret"}}
            )
        assert request.headers["access_token"] == "short-lived-secret"
        return httpx.Response(200, json={"errorcode": 0, "tables": [{"latest": 4000}]})

    result = await fetch(
        query(
            "ext_ths", "real_time_quotation", body={"codes": "000001.SH", "indicators": "latest"}
        ),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert result.status == "snapshot"
    assert "secret" not in json.dumps(result.rows)
    assert all(b"secret" not in raw for raw in result.raw)
    refused = await fetch(query("ext_ths", "refresh", params={}), connections=Secrets())
    assert refused.status == "failed"


def test_external_json_payloads_flatten_primary_lists_into_rows():
    from app.research_web.datahub.providers_external import response_rows

    rates = response_rows(
        b'{"refRates":[{"effectiveDate":"2025-01-09","type":"SOFR"},{"effectiveDate":"2025-01-08","type":"EFFR"}]}',
        "application/json",
    )
    assert [row["type"] for row in rates] == ["SOFR", "EFFR"]
    bls = response_rows(
        b'{"status":"REQUEST_SUCCEEDED","Results":{"series":[{"seriesID":"CUUR0000SA0"}]}}',
        "application/json",
    )
    assert bls == [{"seriesID": "CUUR0000SA0"}]
    page = response_rows(
        json.dumps({"text": "x" * 40000, "format": "page_text"}).encode(), "application/json"
    )
    assert len(page) == 1 and page[0]["format"] == "page_text"


def test_model_facing_sample_is_bounded_while_small_samples_are_untouched():
    from app.research_web.datahub import bounded_sample

    small = [{"a": 1}, {"b": 2}]
    assert bounded_sample(small) == small
    huge = bounded_sample([{"text": "y" * 100000}])
    encoded = json.dumps(huge, ensure_ascii=False).encode()
    assert len(encoded) <= 32768
    assert "样例截断" in encoded.decode()
    medium = bounded_sample([{"pad": "z" * 12000} for _ in range(3)])
    assert len(json.dumps(medium, ensure_ascii=False).encode()) <= 32768
    assert len(medium) <= 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dataset,params",
    [
        ("summary", {}),
        ("datasets", {}),
        ("data", {"dataset": "safe"}),
        ("schema", {"dataset": "safe"}),
        ("batches", {}),
    ],
)
async def test_http_auth_is_blocked_before_secret_read_or_network(dataset, params):
    class Secrets:
        def read_source_secret(self, _source):
            raise AssertionError("HTTP must not read credentials")

    requests = []

    def reply(request):
        requests.append(request)
        raise AssertionError("HTTP must not issue a request")

    result = await fetch(
        query("ext_daole", dataset, params=params),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert result.status == "failed"
    assert result.limitations == ["credential_transport_blocked"]
    assert requests == [] and not result.raw and not result.rows


@pytest.mark.asyncio
async def test_http_auth_probe_does_not_read_credentials():
    from app.research_web.datahub.providers import probe

    class Secrets:
        def source_status(self, _source):
            raise AssertionError("blocked HTTP probe must not inspect credentials")

    result = await probe("ext_daole", connections=Secrets())
    assert result == {"health": "unavailable", "failure_code": "credential_transport_blocked"}
    catalog = build_catalog(
        environ={}, connection_statuses={"ext_daole": {"secret_configured": True}}
    )
    descriptor = next(source for source in catalog["sources"] if source["id"] == "ext_daole")
    assert descriptor["readiness"]["integration_state"] == "credential_transport_blocked"
    assert not descriptor["readiness"]["callable"]
    assert inventory_rows("ext_daole")[0]["status"] == "credential_transport_blocked"


@pytest.mark.asyncio
async def test_https_auth_mock_can_return_business_data():
    class Secrets:
        def read_source_secret(self, source):
            assert source == "ext_tikhub"
            return "synthetic-test-secret"

    def reply(request):
        assert request.url.scheme == "https"
        assert request.headers["authorization"] == "Bearer synthetic-test-secret"
        return httpx.Response(200, json={"data": [{"id": "synthetic"}]})

    result = await fetch(
        query("ext_tikhub", "douyin", params={}),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert result.status == "snapshot" and result.rows == [{"id": "synthetic"}]


def test_sample_budget_counts_json_array_overhead_and_utf8():
    from app.research_web.datahub import bounded_sample

    rows = [{"pad": "x" * 10912} for _ in range(3)]
    assert len(json.dumps(bounded_sample(rows), ensure_ascii=False).encode()) <= 32768
    unicode_rows = [{"pad": "中" * 20000}]
    assert len(json.dumps(bounded_sample(unicode_rows), ensure_ascii=False).encode()) <= 32768


@pytest.mark.asyncio
async def test_https_probe_reads_configuration_record_without_credentials():
    from app.research_web.datahub.providers import probe

    class Connections:
        def source_configuration(self, source):
            assert source == "ext_tikhub"
            return object()

        def source_status(self, _source):
            raise AssertionError("status may read secret")

        def read_source_secret(self, _source):
            raise AssertionError("probe must not read secret")

    result = await probe("ext_tikhub", connections=Connections())
    assert result == {"health": "degraded", "failure_code": "not_live_verified"}


@pytest.mark.asyncio
async def test_ths_business_response_cannot_reflect_refresh_secret():
    class Secrets:
        def read_source_secret(self, _source):
            return json.dumps({"refresh_token": "synthetic-refresh-secret"})

    def reply(request):
        if request.url.path.endswith("get_access_token"):
            return httpx.Response(
                200, json={"errorcode": 0, "data": {"access_token": "synthetic-access-secret"}}
            )
        return httpx.Response(200, json={"data": [{"text": "synthetic-refresh-secret"}]})

    result = await fetch(
        query(
            "ext_ths", "real_time_quotation", body={"codes": "000001.SH", "indicators": "latest"}
        ),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert result.status == "failed" and result.limitations == ["credential_reflection"]
    assert not result.raw and not result.rows


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", [[], {"errorcode": 0, "data": []}, {"errorcode": 0, "data": {"access_token": 123}}]
)
async def test_ths_invalid_auth_payload_fails_closed(payload):
    class Secrets:
        def read_source_secret(self, _source):
            return json.dumps({"refresh_token": "synthetic-refresh-secret"})

    calls = []

    def reply(request):
        calls.append(request.url.path)
        assert request.url.path.endswith("get_access_token")
        return httpx.Response(200, json=payload)

    result = await fetch(
        query("ext_ths", "real_time_quotation", body={}),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert len(calls) == 1
    assert result.status == "failed" and result.limitations == ["vendor_auth_failed"]
    assert not result.raw and not result.rows


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["key", "nested_value", "list_value", "html_text"])
async def test_encoded_credential_reflection_is_rejected_after_parsing(location):
    secret = "synthetic-test-secret"

    class Secrets:
        def read_source_secret(self, source):
            assert source == "ext_tikhub"
            return secret

    if location == "html_text":
        raw = b"<html><body>&#115;ynthetic-test-secret</body></html>"
        content_type = "text/html"
    else:
        payloads = {
            "key": {"data": [{secret: "value"}]},
            "nested_value": {"data": [{"nested": {"value": secret}}]},
            "list_value": {"data": [{"nested": ["ordinary", {"value": secret}]}]},
        }
        raw = json.dumps(payloads[location]).replace(secret, r"\u0073ynthetic-test-secret").encode()
        content_type = "application/json"
    assert secret.encode() not in raw

    def reply(request):
        assert request.url.scheme == "https"
        return httpx.Response(200, content=raw, headers={"content-type": content_type})

    result = await fetch(
        query("ext_tikhub", "douyin", params={}),
        connections=Secrets(),
        transport=httpx.MockTransport(reply),
    )
    assert result.status == "failed"
    assert result.limitations == ["credential_reflection"]
    assert result.rows == [] and result.raw == []
