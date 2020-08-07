import asyncio
import json
from collections import namedtuple

import aiohttp
import pytest
from yarl import URL

from aiorobinhood import RobinhoodClient
from aiorobinhood.urls import ACCOUNTS, LOGIN
from tests import CaseControlledTestServer, FakeResolver, TemporaryCertificate

_RedirectContext = namedtuple("RedirectContext", "add_server session")


def pytest_configure():
    pytest.TIMEOUT = 1
    pytest.ACCOUNT_NUM = "A1B2C3D4"
    pytest.ACCOUNT_URL = "https://api.robinhood.com/accounts/A1B2C3D4/"
    pytest.ACCESS_TOKEN = "access"
    pytest.REFRESH_TOKEN = "refresh"
    pytest.NEXT = URL("https://api.robinhood.com/next/")


@pytest.fixture
async def logged_in_client(http_redirect, ssl_certificate, tmp_path):
    """A logged-in Robinhood client/server fixture."""
    async with CaseControlledTestServer(ssl=ssl_certificate.server_context()) as server:
        http_redirect.add_server("api.robinhood.com", 443, server.port)
        client = RobinhoodClient(
            timeout=pytest.TIMEOUT,
            session=http_redirect.session,
            session_file=str(tmp_path / ".aiorobinhood.pickle"),
        )

        task = asyncio.create_task(client.login(username="robin", password="hood"))
        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert request.path == LOGIN.path
        server.send_response(
            request,
            content_type="application/json",
            text=json.dumps(
                {
                    "access_token": pytest.ACCESS_TOKEN,
                    "refresh_token": pytest.REFRESH_TOKEN,
                }
            ),
        )

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "GET"
        assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
        assert request.path == ACCOUNTS.path
        server.send_response(
            request,
            content_type="application/json",
            text=json.dumps(
                {
                    "results": [
                        {
                            "url": pytest.ACCOUNT_URL,
                            "account_number": pytest.ACCOUNT_NUM,
                        }
                    ]
                }
            ),
        )

        result = await asyncio.wait_for(task, pytest.TIMEOUT)
        assert result is None
        yield client, server


@pytest.fixture
async def logged_out_client(http_redirect, ssl_certificate):
    """A logged-out Robinhood client/server fixture."""
    async with CaseControlledTestServer(ssl=ssl_certificate.server_context()) as server:
        http_redirect.add_server("api.robinhood.com", 443, server.port)
        client = RobinhoodClient(timeout=pytest.TIMEOUT, session=http_redirect.session)
        yield client, server


@pytest.fixture
async def http_redirect(ssl_certificate):
    """An HTTP ClientSession fixture that redirects requests to local test servers."""
    resolver = FakeResolver()
    connector = aiohttp.TCPConnector(
        resolver=resolver, ssl=ssl_certificate.client_context(), use_dns_cache=False
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        yield _RedirectContext(add_server=resolver.add, session=session)


@pytest.fixture(scope="session")
def ssl_certificate():
    """Self-signed certificate fixture, used for local server tests."""
    with TemporaryCertificate() as certificate:
        yield certificate
