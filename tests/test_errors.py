import asyncio

import aiohttp
import pytest
from yarl import URL

from aiorobinhood import (
    ClientAPIError,
    ClientRequestError,
    ClientUninitializedError,
    RobinhoodClient,
)
from tests import CaseControlledTestServer, TemporaryCertificate


@pytest.mark.asyncio
async def test_request_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.request(method="GET", url=pytest.NEXT))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.path == pytest.NEXT.path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_request_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.request(method="GET", url=pytest.NEXT))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.path == pytest.NEXT.path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_request_connection_failure(http_redirect, unused_tcp_port):
    http_redirect.add_server("api.robinhood.com", 443, unused_tcp_port)
    client = RobinhoodClient(timeout=pytest.TIMEOUT, session=http_redirect.session)

    with pytest.raises(ClientRequestError) as exc_info:
        await client.request(method="GET", url=pytest.NEXT)
    assert isinstance(exc_info.value.__cause__, aiohttp.ClientConnectorError)


@pytest.mark.asyncio
async def test_request_invalid_certificate(http_redirect):
    with TemporaryCertificate() as bad_cert:
        async with CaseControlledTestServer(ssl=bad_cert.server_context()) as server:
            http_redirect.add_server("api.robinhood.com", 443, server.port)
            client = RobinhoodClient(
                timeout=pytest.TIMEOUT, session=http_redirect.session
            )

            with pytest.raises(ClientRequestError) as exc_info:
                await client.request(method="GET", url=pytest.NEXT)
            assert isinstance(
                exc_info.value.__cause__, aiohttp.ClientConnectorCertificateError
            )


@pytest.mark.asyncio
async def test_request_uninitialized_client():
    client = RobinhoodClient(timeout=pytest.TIMEOUT)
    with pytest.raises(ClientUninitializedError):
        await client.request(method="GET", url=pytest.NEXT)


@pytest.mark.asyncio
async def test_request_bad_origin(logged_in_client):
    client, _ = logged_in_client
    with pytest.raises(ValueError):
        await client.request(method="GET", url=URL("https://foobar.com"))
