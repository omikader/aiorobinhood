import asyncio
import json

import pytest

from aiorobinhood import (
    ClientAPIError,
    ClientRequestError,
    HistoricalInterval,
    HistoricalSpan,
)
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
        request, content_type="application/json", text=json.dumps({"results": [{}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == {}


@pytest.mark.asyncio
async def test_get_account_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_account())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ACCOUNTS.path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_account_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_account())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ACCOUNTS.path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_get_portfolio(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_portfolio())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == PORTFOLIOS.path
    server.send_response(
        request, content_type="application/json", text=json.dumps({"results": [{}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == {}


@pytest.mark.asyncio
async def test_get_portfolio_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_portfolio())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == PORTFOLIOS.path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_portfolio_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_portfolio())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == PORTFOLIOS.path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


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


@pytest.mark.asyncio
async def test_get_historical_portfolio_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.get_historical_portfolio(
            interval=HistoricalInterval.FIVE_MIN, span=HistoricalSpan.DAY
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (PORTFOLIOS / "historicals" / f"{pytest.ACCOUNT_NUM}/").path
    assert request.query["bounds"] == "regular"
    assert request.query["interval"] == HistoricalInterval.FIVE_MIN.value
    assert request.query["span"] == HistoricalSpan.DAY.value
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_historical_portfolio_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.get_historical_portfolio(
            interval=HistoricalInterval.FIVE_MIN, span=HistoricalSpan.DAY
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (PORTFOLIOS / "historicals" / f"{pytest.ACCOUNT_NUM}/").path
    assert request.query["bounds"] == "regular"
    assert request.query["interval"] == HistoricalInterval.FIVE_MIN.value
    assert request.query["span"] == HistoricalSpan.DAY.value

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)
