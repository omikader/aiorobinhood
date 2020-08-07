import asyncio
import json

import pytest

from aiorobinhood import ClientAPIError, ClientRequestError
from aiorobinhood.urls import INSTRUMENTS, ORDERS, QUOTES


@pytest.mark.asyncio
async def test_get_orders(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_orders())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": str(pytest.NEXT), "results": [{"foo": "bar"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == pytest.NEXT.path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"baz": "quux"}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == [{"foo": "bar"}, {"baz": "quux"}]


@pytest.mark.asyncio
async def test_get_orders_api_error(logged_in_client):
    client, server = logged_in_client
    order_id = "12345"
    task = asyncio.create_task(client.get_orders(order_id))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (ORDERS / f"{order_id}/").path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_orders_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_orders())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_cancel_order(logged_in_client):
    client, server = logged_in_client
    order_id = "12345"
    task = asyncio.create_task(client.cancel_order(order_id))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (ORDERS / order_id / "cancel/").path
    server.send_response(request, content_type="application/json")

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result is None


@pytest.mark.asyncio
async def test_cancel_order_api_error(logged_in_client):
    client, server = logged_in_client
    order_id = "12345"
    task = asyncio.create_task(client.cancel_order(order_id))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (ORDERS / order_id / "cancel/").path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_cancel_order_timeout_error(logged_in_client):
    client, server = logged_in_client
    order_id = "12345"
    task = asyncio.create_task(client.cancel_order(order_id))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (ORDERS / order_id / "cancel/").path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_order_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.place_order())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    assert (await request.json())["account"] == pytest.ACCOUNT_URL
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_order_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.place_order())

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    assert (await request.json())["account"] == pytest.ACCOUNT_URL

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_place_limit_buy_order(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_limit_buy_order(symbol="ABCD", price=12.50, quantity=1)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"url": "<>"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 12.5
    assert request_json["quantity"] == 1
    assert request_json["side"] == "buy"
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "immediate"
    assert request_json["type"] == "limit"
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_limit_sell_order(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_limit_sell_order(symbol="ABCD", price=12.50, quantity=1)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"url": "<>"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 12.5
    assert request_json["quantity"] == 1
    assert request_json["side"] == "sell"
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "immediate"
    assert request_json["type"] == "limit"
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_market_buy_order_by_amount(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_market_buy_order(symbol="ABCD", amount=12.255)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == QUOTES.path
    assert request.query["symbols"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"results": [{"instrument": "<>", "ask_price": "1.0"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 1.0
    assert request_json["quantity"] == 12.255
    assert request_json["side"] == "buy"
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "immediate"
    assert request_json["type"] == "market"
    assert request_json["dollar_based_amount"] == {
        "currency_code": "USD",
        "amount": 12.26,
    }
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_market_buy_order_by_quantity(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_market_buy_order(symbol="ABCD", quantity=2.5)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == QUOTES.path
    assert request.query["symbols"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"results": [{"instrument": "<>", "ask_price": "1.0"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 1.0
    assert request_json["quantity"] == 2.5
    assert request_json["side"] == "buy"
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "immediate"
    assert request_json["type"] == "market"
    assert "dollar_based_amount" not in request_json
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_market_buy_order_value_error(logged_in_client):
    client, _ = logged_in_client
    with pytest.raises(ValueError):
        await client.place_market_buy_order(symbol="ABCD")
    with pytest.raises(ValueError):
        await client.place_market_buy_order(symbol="ABCD", amount=10.0, quantity=2.5)


@pytest.mark.asyncio
async def test_place_market_sell_order_by_amount(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_market_sell_order(symbol="ABCD", amount=12.255)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == QUOTES.path
    assert request.query["symbols"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"results": [{"instrument": "<>", "bid_price": "1.0"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 1.0
    assert request_json["quantity"] == 12.255
    assert request_json["side"] == "sell"
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "immediate"
    assert request_json["type"] == "market"
    assert request_json["dollar_based_amount"] == {
        "currency_code": "USD",
        "amount": 12.26,
    }
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_market_sell_order_by_quantity(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_market_sell_order(symbol="ABCD", quantity=2.5)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == QUOTES.path
    assert request.query["symbols"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"results": [{"instrument": "<>", "bid_price": "1.0"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 1.0
    assert request_json["quantity"] == 2.5
    assert request_json["side"] == "sell"
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "immediate"
    assert request_json["type"] == "market"
    assert "dollar_based_amount" not in request_json
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_market_sell_order_value_error(logged_in_client):
    client, _ = logged_in_client
    with pytest.raises(ValueError):
        await client.place_market_sell_order(symbol="ABCD")
    with pytest.raises(ValueError):
        await client.place_market_sell_order(symbol="ABCD", amount=10.0, quantity=2.5)


@pytest.mark.asyncio
async def test_place_stop_buy_order(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_stop_buy_order(symbol="ABCD", price=10, quantity=1)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"url": "<>"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 10
    assert request_json["quantity"] == 1
    assert request_json["side"] == "buy"
    assert request_json["stop_price"] == 10
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "stop"
    assert request_json["type"] == "market"
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_stop_sell_order(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_stop_sell_order(symbol="ABCD", price=10, quantity=1)
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"url": "<>"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["quantity"] == 1
    assert request_json["side"] == "sell"
    assert request_json["stop_price"] == 10
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "stop"
    assert request_json["type"] == "market"
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_stop_limit_buy_order(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_stop_limit_buy_order(
            symbol="ABCD", price=10, stop_price=12.5, quantity=1
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"url": "<>"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 10
    assert request_json["quantity"] == 1
    assert request_json["side"] == "buy"
    assert request_json["stop_price"] == 12.5
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "stop"
    assert request_json["type"] == "limit"
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"


@pytest.mark.asyncio
async def test_place_stop_limit_sell_order(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.place_stop_limit_sell_order(
            symbol="ABCD", price=8.1, stop_price=8, quantity=1
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"next": None, "results": [{"url": "<>"}]}),
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == ORDERS.path
    request_json = await request.json()
    assert request_json["account"] == pytest.ACCOUNT_URL
    assert request_json["instrument"] == "<>"
    assert request_json["price"] == 8.1
    assert request_json["quantity"] == 1
    assert request_json["side"] == "sell"
    assert request_json["stop_price"] == 8
    assert request_json["symbol"] == "ABCD"
    assert request_json["trigger"] == "stop"
    assert request_json["type"] == "limit"
    server.send_response(
        request,
        status=201,
        content_type="application/json",
        text=json.dumps({"id": "ID"}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == "ID"
