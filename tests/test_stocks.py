import asyncio
import json

import pytest

from aiorobinhood import (
    ClientAPIError,
    ClientRequestError,
    HistoricalInterval,
    HistoricalSpan,
)
from aiorobinhood.urls import (
    FUNDAMENTALS,
    HISTORICALS,
    INSTRUMENTS,
    QUOTES,
    RATINGS,
    TAGS,
)


@pytest.mark.asyncio
async def test_get_fundamentals(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_fundamentals(symbols=["ABCD"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == FUNDAMENTALS.path
    assert request.query["symbols"] == "ABCD"
    server.send_response(
        request, content_type="application/json", text=json.dumps({"results": [{}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == [{}]


@pytest.mark.asyncio
async def test_get_fundamentals_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_fundamentals(instruments=["<>"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == FUNDAMENTALS.path
    assert request.query["instruments"] == "<>"
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_fundamentals_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_fundamentals(symbols=["ABCD"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == FUNDAMENTALS.path
    assert request.query["symbols"] == "ABCD"

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_get_fundamentals_value_error(logged_in_client):
    client, _ = logged_in_client
    with pytest.raises(ValueError):
        await client.get_fundamentals()
    with pytest.raises(ValueError):
        await client.get_fundamentals(symbols=["ABCD"], instruments=["<>"])


@pytest.mark.asyncio
async def test_get_instruments(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_instruments(symbol="ABCD"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"
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
async def test_get_instruments_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_instruments(ids=["12345"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["ids"] == "12345"
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_instruments_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_instruments(symbol="ABCD"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == INSTRUMENTS.path
    assert request.query["symbol"] == "ABCD"

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_get_instruments_value_error(logged_in_client):
    client, _ = logged_in_client
    with pytest.raises(ValueError):
        await client.get_instruments()
    with pytest.raises(ValueError):
        await client.get_instruments(symbol="ABCD", ids=["12345"])


@pytest.mark.asyncio
async def test_get_quotes(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_quotes(symbols=["ABCD"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == QUOTES.path
    assert request.query["symbols"] == "ABCD"
    server.send_response(
        request, content_type="application/json", text=json.dumps({"results": [{}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == [{}]


@pytest.mark.asyncio
async def test_get_quotes_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_quotes(instruments=["<>"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == QUOTES.path
    assert request.query["instruments"] == "<>"
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_quotes_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_quotes(symbols=["ABCD"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == QUOTES.path
    assert request.query["symbols"] == "ABCD"

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_get_quotes_value_error(logged_in_client):
    client, _ = logged_in_client
    with pytest.raises(ValueError):
        await client.get_quotes()
    with pytest.raises(ValueError):
        await client.get_quotes(symbols=["ABCD"], instruments=["<>"])


@pytest.mark.asyncio
async def test_get_historical_quotes(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.get_historical_quotes(
            interval=HistoricalInterval.FIVE_MIN,
            span=HistoricalSpan.DAY,
            symbols=["ABCD"],
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == HISTORICALS.path
    assert request.query["bounds"] == "regular"
    assert request.query["interval"] == HistoricalInterval.FIVE_MIN.value
    assert request.query["span"] == HistoricalSpan.DAY.value
    assert request.query["symbols"] == "ABCD"
    server.send_response(
        request, content_type="application/json", text=json.dumps({"results": [{}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == [{}]


@pytest.mark.asyncio
async def test_get_historical_quotes_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.get_historical_quotes(
            interval=HistoricalInterval.FIVE_MIN,
            span=HistoricalSpan.DAY,
            extended_hours=True,
            instruments=["<>"],
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == HISTORICALS.path
    assert request.query["bounds"] == "extended"
    assert request.query["interval"] == HistoricalInterval.FIVE_MIN.value
    assert request.query["span"] == HistoricalSpan.DAY.value
    assert request.query["instruments"] == "<>"
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_historical_quotes_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(
        client.get_historical_quotes(
            interval=HistoricalInterval.FIVE_MIN,
            span=HistoricalSpan.DAY,
            symbols=["ABCD"],
        )
    )

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == HISTORICALS.path
    assert request.query["bounds"] == "regular"
    assert request.query["interval"] == HistoricalInterval.FIVE_MIN.value
    assert request.query["span"] == HistoricalSpan.DAY.value
    assert request.query["symbols"] == "ABCD"

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_get_historical_quotes_value_error(logged_in_client):
    client, _ = logged_in_client
    with pytest.raises(ValueError):
        await client.get_historical_quotes()
    with pytest.raises(ValueError):
        await client.get_historical_quotes(symbols=["ABCD"], instruments=["<>"])


@pytest.mark.asyncio
async def test_get_ratings(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_ratings(ids=["12345", "67890"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == RATINGS.path
    assert request.query["ids"] == "12345,67890"
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
async def test_get_ratings_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_ratings(ids=["12345", "67890"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == RATINGS.path
    assert request.query["ids"] == "12345,67890"
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_ratings_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_ratings(ids=["12345", "67890"]))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == RATINGS.path
    assert request.query["ids"] == "12345,67890"

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_get_tags(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_tags(id_="12345"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (TAGS / "instrument" / "12345/").path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"tags": [{"slug": "foo"}]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == ["foo"]


@pytest.mark.asyncio
async def test_get_tags_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_tags(id_="12345"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (TAGS / "instrument" / "12345/").path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_tags_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_tags(id_="12345"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (TAGS / "instrument" / "12345/").path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_get_tag_members(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_tag_members(tag="foo"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (TAGS / "tag" / "foo/").path
    server.send_response(
        request,
        content_type="application/json",
        text=json.dumps({"instruments": ["<>"]}),
    )

    result = await asyncio.wait_for(task, pytest.TIMEOUT)
    assert result == ["<>"]


@pytest.mark.asyncio
async def test_get_tag_members_api_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_tag_members(tag="foo"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (TAGS / "tag" / "foo/").path
    server.send_response(request, status=400, content_type="application/json")

    with pytest.raises(ClientAPIError):
        await task


@pytest.mark.asyncio
async def test_get_tag_members_timeout_error(logged_in_client):
    client, server = logged_in_client
    task = asyncio.create_task(client.get_tag_members(tag="foo"))

    request = await server.receive_request(timeout=pytest.TIMEOUT)
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {pytest.ACCESS_TOKEN}"
    assert request.path == (TAGS / "tag" / "foo/").path

    with pytest.raises(ClientRequestError) as exc_info:
        await asyncio.sleep(pytest.TIMEOUT + 1)
        await task
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)
