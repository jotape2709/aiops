import io
import json
import socket
from datetime import UTC, datetime
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest

from src.integrations.ripestat import (
    RipeStatError,
    _parse_retry_after,
    fetch_ripestat_data,
    format_retry_after,
)


def raw_ripestat_payload(
    *,
    status: str = "ok",
    v4_seeing: int = 323,
    v4_total: int = 325,
    v6_seeing: int = 317,
    v6_total: int = 317,
    v4_prefixes: int = 1,
    v6_prefixes: int = 1,
    first_seen_time: str = "2002-03-01T16:00:00",
    last_seen_time: str = "2026-09-24T08:00:00",
    query_time: str = "2026-09-24T08:00:00",
    resource: str = "22548",
) -> dict:
    return {
        "status": status,
        "status_code": 200,
        "messages": [["info", "Results exclude routes with very low visibility."]],
        "data": {
            "first_seen": {
                "prefix": "200.160.0.0/20",
                "origin": resource,
                "time": first_seen_time,
            },
            "last_seen": {
                "prefix": "200.160.0.0/20",
                "origin": resource,
                "time": last_seen_time,
            },
            "visibility": {
                "v4": {
                    "ris_peers_seeing": v4_seeing,
                    "total_ris_peers": v4_total,
                },
                "v6": {
                    "ris_peers_seeing": v6_seeing,
                    "total_ris_peers": v6_total,
                },
            },
            "announced_space": {
                "v4": {
                    "prefixes": v4_prefixes,
                    "ips": 4096,
                },
                "v6": {
                    "prefixes": v6_prefixes,
                    "48s": 65536,
                },
            },
            "observed_neighbours": 2000,
            "resource": resource,
            "query_time": query_time,
        },
    }


def ripestat_response(data: dict) -> io.BytesIO:
    return io.BytesIO(json.dumps(data).encode("utf-8"))


def test_success_and_request_contract(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        url = urlparse(request.full_url)
        params = parse_qs(url.query)
        resource = params.get("resource", [""])[0]
        return ripestat_response(raw_ripestat_payload(resource=resource))

    result = fetch_ripestat_data(
        opener=opener,
        timeout=8,
        request_interval=0.0,
    )
    assert len(result.records) == 3
    assert result.requests_made == 3
    assert result.invalid_count == 0
    assert result.fetched_asns == ("AS22548", "AS1251", "AS1916")
    assert result.failed_asns == ()

    assert len(calls) == 3
    for request, timeout in calls:
        assert timeout == 8
        assert request.get_method() == "GET"
        assert "aiops-network-dashboard" in request.get_header("User-agent")
        url = urlparse(request.full_url)
        assert url.path == "/data/routing-status/data.json"
        query = parse_qs(url.query)
        assert "resource" in query
        assert query["sourceapp"] == ["aiops-network-dashboard"]


def test_asn_isolation_middle_503_yields_partial_result(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        if "AS1251" in request.full_url:
            raise HTTPError(request.full_url, 503, "Service Unavailable", {}, None)
        return ripestat_response(raw_ripestat_payload(resource="AS22548"))

    result = fetch_ripestat_data(opener=opener, sleep=lambda _: None)
    assert len(result.records) == 2
    assert result.fetched_asns == ("AS22548", "AS1916")
    assert result.failed_asns == ("AS1251",)
    assert result.requests_made == 3


def test_rate_limit_429_in_middle_interrupts_and_returns_partial_with_retry_after(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        if "AS22548" in request.full_url:
            return ripestat_response(raw_ripestat_payload(resource="AS22548"))
        headers = Message()
        headers["Retry-After"] = "60"
        raise HTTPError(request.full_url, 429, "Too Many Requests", headers, None)

    result = fetch_ripestat_data(opener=opener, sleep=lambda _: None)
    assert len(result.records) == 1
    assert result.fetched_asns == ("AS22548",)
    assert result.failed_asns == ("AS1251", "AS1916")
    assert result.retry_after_seconds == 60


def test_rate_limit_429_on_first_asn_raises_error(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        headers = Message()
        headers["Retry-After"] = "1560"
        raise HTTPError(request.full_url, 429, "Too Many Requests", headers, None)

    with pytest.raises(RipeStatError) as exc_info:
        fetch_ripestat_data(opener=opener)
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds == 1560
    assert "tente novamente em ~26 min" in str(exc_info.value)
    assert exc_info.value.fetched_asns == ()
    assert exc_info.value.failed_asns == ("AS22548", "AS1251", "AS1916")


def test_target_deduplication(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        return ripestat_response(raw_ripestat_payload())

    targets = (
        ("AS22548", "NIC.br"),
        ("as22548", "NIC.br duplicado"),
        ("AS1916", "RNP"),
    )
    result = fetch_ripestat_data(asns=targets, opener=opener, request_interval=0.0)
    assert len(calls) == 2
    assert result.fetched_asns == ("AS22548", "AS1916")


def test_seeing_greater_than_total_treated_as_invalid(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        return ripestat_response(
            raw_ripestat_payload(v4_seeing=350, v4_total=325, v6_seeing=400, v6_total=317)
        )

    result = fetch_ripestat_data(asns=(("AS22548", "NIC.br"),), opener=opener)
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.visibility.v4_seeing is None
    assert rec.visibility.v4_total is None
    assert rec.visibility.v6_seeing is None
    assert rec.visibility.v6_total is None
    assert result.invalid_count >= 2


def test_malformed_seen_times_increment_invalid_count(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        data = raw_ripestat_payload()
        data["data"]["first_seen"] = {"no_time": 123}
        data["data"]["last_seen"] = 9999
        return ripestat_response(data)

    result = fetch_ripestat_data(asns=(("AS22548", "NIC.br"),), opener=opener)
    assert len(result.records) == 1
    assert result.records[0].first_seen is None
    assert result.records[0].last_seen is None
    assert result.invalid_count == 2


def test_budget_exceeded_with_records(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    timeline = [0.0, 5.0, 25.0]

    def fake_clock():
        return timeline.pop(0) if timeline else 30.0

    def opener(request, timeout):
        return ripestat_response(raw_ripestat_payload())

    result = fetch_ripestat_data(
        opener=opener,
        total_budget=20.0,
        clock=fake_clock,
        sleep=lambda _: None,
    )
    assert len(result.records) == 1
    assert result.fetched_asns == ("AS22548",)
    assert result.failed_asns == ("AS1251", "AS1916")


def test_budget_exceeded_before_any_request(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    timeline = [0.0, 15.0]

    with pytest.raises(RipeStatError) as exc_info:
        fetch_ripestat_data(
            opener=lambda req, timeout: ripestat_response(raw_ripestat_payload()),
            total_budget=10.0,
            clock=lambda: timeline.pop(0) if timeline else 30.0,
        )
    assert "Orçamento de tempo excedido" in str(exc_info.value)
    assert exc_info.value.fetched_asns == ()
    assert exc_info.value.failed_asns == ("AS22548", "AS1251", "AS1916")


def test_format_retry_after() -> None:
    assert format_retry_after(None) == ""
    assert format_retry_after(45) == "~45 s"
    assert format_retry_after(59) == "~59 s"
    assert format_retry_after(60) == "~1 min"
    assert format_retry_after(1560) == "~26 min"
    assert format_retry_after(0) == "~0 s"


def test_parse_retry_after_formats() -> None:
    assert _parse_retry_after("120") == 120
    assert _parse_retry_after("  15  ") == 15
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("") is None
    assert _parse_retry_after("abc") is None

    # Formato HTTP-date
    now = datetime(2026, 9, 24, 8, 0, 0, tzinfo=UTC)
    future_date = "Thu, 24 Sep 2026 08:01:30 GMT"
    assert _parse_retry_after(future_date, now_fn=lambda: now) == 90


def test_all_asns_failing_raises_ripestat_error(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener_always_fails(request, timeout):
        raise URLError("dns resolution failed")

    with pytest.raises(RipeStatError) as exc_info:
        fetch_ripestat_data(opener=opener_always_fails)
    assert exc_info.value.fetched_asns == ()
    assert exc_info.value.failed_asns == ("AS22548", "AS1251", "AS1916")


def test_prohibited_words_not_in_error_or_messages(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener_500(request, timeout):
        raise HTTPError(request.full_url, 500, "Internal Server Error", {}, None)

    with pytest.raises(RipeStatError) as exc_info:
        fetch_ripestat_data(opener=opener_500)

    for word in ("incidente", "queda", "falha", "fora do ar"):
        assert word not in str(exc_info.value).lower()
