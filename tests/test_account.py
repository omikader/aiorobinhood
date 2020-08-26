import asyncio
import json

import pytest

from aiorobinhood.urls import POSITIONS, WATCHLISTS


@pytest.mark.asyncio
async def test_get_positions(logged_in_client):
    client, server = logged_in_client
    task = asyncio.ensure_future(client.get_positions())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == POSITIONS.path
    assert request.query["nonzero"] == "true"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": str(pytest.NEXT), "results": [{"foo": "bar"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.method == "GET"
    assert request.path == pytest.NEXT.path
    assert "nonzero" not in request.query
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"baz": "quux"}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == [{"foo": "bar"}, {"baz": "quux"}]


@pytest.mark.asyncio
async def test_get_watchlist(logged_in_client):
    client, server = logged_in_client
    task = asyncio.ensure_future(client.get_watchlist(pages=2))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (WATCHLISTS / "Default/").path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": str(pytest.NEXT), "results": [{"instrument": "<>"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == pytest.NEXT.path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": str(pytest.NEXT), "results": [{"instrument": "><"}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == ["<>", "><"]


@pytest.mark.asyncio
async def test_add_to_watchlist(logged_in_client):
    client, server = logged_in_client
    task = asyncio.ensure_future(client.add_to_watchlist(instrument="<>"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (WATCHLISTS / "Default/").path
    assert (await request.json())["instrument"] == "<>"
    server.send_response(request, status=201, content_type="application/json")

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result is None


@pytest.mark.asyncio
async def test_remove_from_watchlist(logged_in_client):
    client, server = logged_in_client
    task = asyncio.ensure_future(client.remove_from_watchlist(id_="12345"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "DELETE"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (WATCHLISTS / "Default" / "12345/").path
    server.send_response(request, status=204, content_type="application/json")

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result is None
