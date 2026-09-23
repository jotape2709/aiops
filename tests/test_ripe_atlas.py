import io
import json
import socket
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from src.integrations.ripe_atlas import RipeAtlasError, fetch_br_probes


def probe(probe_id: int = 1) -> dict:
    return {
        "id": probe_id,
        "status": {"id": 1},
        "asn_v4": 64500,
        "asn_v6": None,
        "geometry": {"type": "Point", "coordinates": [-46.63, -23.55]},
        "is_anchor": False,
    }


def response(results: list[dict], next_page: str | None = None, count: int = 1) -> io.BytesIO:
    return io.BytesIO(json.dumps({"results": results, "next": next_page, "count": count}).encode())


def test_success_and_request_contract(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return response([probe()])

    result = fetch_br_probes(opener=opener, page_size=100, max_pages=2, timeout=7)
    assert len(result.probes) == 1
    assert result.probes[0].lat == -23.55
    assert result.requests_made == 1
    assert result.invalid_count == 0
    request, timeout = calls[0]
    params = parse_qs(urlparse(request.full_url).query)
    assert urlparse(request.full_url).path == "/api/v2/probes/"
    assert params == {
        "country_code": ["BR"],
        "fields": ["id,status,asn_v4,asn_v6,geometry,is_anchor"],
        "page_size": ["100"],
        "page": ["1"],
    }
    assert request.get_method() == "GET"
    assert "aiops-network-dashboard" in request.get_header("User-agent")
    assert timeout == 7


def test_pagination_stops_at_max_pages(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    pages = []

    def opener(request, timeout):
        pages.append(parse_qs(urlparse(request.full_url).query)["page"][0])
        return response([probe(int(pages[-1]))], next_page="https://atlas.ripe.net/next", count=999)

    result = fetch_br_probes(opener=opener, page_size=500, max_pages=2)
    assert pages == ["1", "2"]
    assert result.requests_made == 2
    assert result.truncated
    assert len(result.probes) == 2


def test_invalid_probe_is_discarded_but_valid_probes_survive(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    result = fetch_br_probes(
        opener=lambda request, timeout: response([probe(1), {"id": 2}, probe(3)], count=3)
    )
    assert [item.probe_id for item in result.probes] == [1, 3]
    assert result.invalid_count == 1
    assert result.reported_count == 3


@pytest.mark.parametrize(
    "opener",
    [
        lambda request, timeout: (_ for _ in ()).throw(
            HTTPError(request.full_url, 503, "down", {}, None)
        ),
        lambda request, timeout: (_ for _ in ()).throw(HTTPException("bad response")),
        lambda request, timeout: (_ for _ in ()).throw(TimeoutError()),
        lambda request, timeout: io.BytesIO(b"{bad json"),
        lambda request, timeout: io.BytesIO(json.dumps({"results": {}, "count": 1}).encode()),
    ],
)
def test_envelope_and_transport_failures_are_typed(monkeypatch, opener) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    with pytest.raises(RipeAtlasError):
        fetch_br_probes(opener=opener)
