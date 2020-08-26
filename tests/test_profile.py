import asyncio
import json

import pytest

from aiorobinhood import HistoricalInterval, HistoricalSpan
from aiorobinhood.urls import ACCOUNTS, PORTFOLIOS


@pytest.mark.asyncio
async def test_get_account(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_account())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ACCOUNTS.path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"results": [{}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == {}


@pytest.mark.asyncio
async def test_get_portfolio(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_portfolio())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == PORTFOLIOS.path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"results": [{}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == {}


@pytest.mark.asyncio
async def test_get_historical_portfolio(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.get_historical_portfolio(
            interval=HistoricalInterval.FIVE_MIN,
            span=HistoricalSpan.DAY,
            extended_hours=True,
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (PORTFOLIOS / "historicals" / f"{pytest.ACCOUNT_NUM}/").path
    assert request.query["bounds"] == "extended"
    assert request.query["interval"] == HistoricalInterval.FIVE_MIN.value
    assert request.query["span"] == HistoricalSpan.DAY.value
    server.send_response(request, content_type="application/json", text=json.dumps({}))

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == {}
