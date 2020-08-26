import asyncio
import json
import pickle
import sys
from contextlib import contextmanager
from io import StringIO

import pytest

from aiorobinhood import ClientAPIError, ClientUnauthenticatedError
from aiorobinhood.urls import ACCOUNTS, CHALLENGE, LOGIN, LOGOUT


@contextmanager
def replace_input(target):
    orig = sys.stdin
    sys.stdin = target
    yield
    sys.stdin = orig


@pytest.mark.asyncio
async def test_login_sfa_flow(logged_out_client):
    client, server = logged_out_client
    challenge_code = "123456"
    challenge_id = "abcdef"

    with replace_input(StringIO(challenge_code)):
        task = asyncio.create_task(client.login(username="robin", password="hood"))

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert request.path == LOGIN.path
        server.send_response(
            request,
            status=400,
            content_type="application/json",
            text=json.dumps(
                {"challenge": {"id": challenge_id, "remaining_attempts": 3}}
            ),
        )

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert (await request.json())["response"] == challenge_code
        assert request.path == f"{CHALLENGE.path}{challenge_id}/respond/"
        server.send_response(
            request,
            content_type="application/json",
            text=json.dumps({"id": challenge_id}),
        )

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


@pytest.mark.asyncio
async def test_login_mfa_flow(logged_out_client):
    client, server = logged_out_client
    mfa_code = "123456"

    with replace_input(StringIO(mfa_code)):
        task = asyncio.create_task(client.login(username="robin", password="hood"))

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert request.path == LOGIN.path
        server.send_response(
            request,
            content_type="application/json",
            text=json.dumps({"mfa_required": True, "mfa_type": "sms"}),
        )

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert (await request.json())["mfa_code"] == mfa_code
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


@pytest.mark.asyncio
async def test_login_api_error(logged_out_client):
    client, server = logged_out_client
    challenge_code = "123456"

    with replace_input(StringIO(challenge_code)):
        task = asyncio.create_task(client.login(username="robin", password="hood"))

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert request.path == LOGIN.path
        server.send_response(
            request,
            status=400,
            content_type="application/json",
            text=json.dumps({}),
        )

        with pytest.raises(ClientAPIError):
            await task


@pytest.mark.asyncio
async def test_login_sfa_zero_challenge_attempts(logged_out_client):
    client, server = logged_out_client
    challenge_code = "123456"
    challenge_id = "abcdef"

    with replace_input(StringIO(challenge_code)):
        task = asyncio.create_task(client.login(username="robin", password="hood"))

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert request.path == LOGIN.path
        server.send_response(
            request,
            status=400,
            content_type="application/json",
            text=json.dumps(
                {"challenge": {"id": challenge_id, "remaining_attempts": 1}}
            ),
        )

        request = await server.receive_request(timeout=pytest.TIMEOUT)
        assert request.method == "POST"
        assert (await request.json())["response"] == challenge_code
        assert request.path == f"{CHALLENGE.path}{challenge_id}/respond/"
        server.send_response(
            request,
            status=400,
            content_type="application/json",
            text=json.dumps(
                {"challenge": {"id": challenge_id, "remaining_attempts": 0}}
            ),
        )

        with pytest.raises(ClientAPIError):
            await task


@pytest.mark.asyncio
async def test_logout(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.logout())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert (await request.json())["token"] == pytest.REFRESH_TOKEN
    assert request.path == LOGOUT.path
    server.send_response(request, content_type="application/json")

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert client._access_token is None
    assert client._refresh_token is None
    assert result is None


@pytest.mark.asyncio
async def test_logout_unauthenticated_client(logged_out_client):
    client, _ = logged_out_client
    with pytest.raises(ClientUnauthenticatedError):
        await client.logout()


@pytest.mark.asyncio
async def test_refresh(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.refresh())

    assert client._access_token == f"Bearer {pytest.ACCESS_TOKEN}"
    assert client._refresh_token == pytest.REFRESH_TOKEN

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    request_json = await request.json()
    assert request_json["grant_type"] == "refresh_token"
    assert request_json["refresh_token"] == pytest.REFRESH_TOKEN
    assert request.path == LOGIN.path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"access_token": "foo", "refresh_token": "bar"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert client._access_token == "Bearer foo"
    assert client._refresh_token == "bar"
    assert result is None


@pytest.mark.asyncio
async def test_dump(logged_in_client):
    client, _ = logged_in_client
    await client.dump()

    with open(client._session_file, "rb") as f:
        data = pickle.load(f)
        assert data["access_token"] == f"Bearer {pytest.ACCESS_TOKEN}"
        assert data["refresh_token"] == pytest.REFRESH_TOKEN


@pytest.mark.asyncio
async def test_load(logged_in_client):
    client, server = logged_in_client
    await client.dump()
    task = asyncio.create_task(client.load())

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
                    {"url": pytest.ACCOUNT_URL, "account_number": pytest.ACCOUNT_NUM}
                ]
            }
        ),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert client._access_token == f"Bearer {pytest.ACCESS_TOKEN}"
    assert client._refresh_token == pytest.REFRESH_TOKEN
    assert result is None
