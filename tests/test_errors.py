import asyncio

import pytest

from aiorobinhood import ClientAPIError, ClientRequestError


@pytest.mark.asyncio
async def test_request_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.request("GET", pytest.NEXT))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.path == pytest.NEXT.path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_request_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.request("GET", pytest.NEXT))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.path == pytest.NEXT.path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)
