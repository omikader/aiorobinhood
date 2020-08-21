import aiohttp
import pytest

from aiorobinhood import ClientUninitializedError, RobinhoodClient


@pytest.mark.asyncio
async def test_async_context_manager():
    async with RobinhoodClient(timeout=pytest.TIMEOUT) as client:
        assert client._session is not None
        assert isinstance(client._session, aiohttp.ClientSession)


@pytest.mark.asyncio
async def test_async_context_manager_client_uninitialized_error():
    with pytest.raises(ClientUninitializedError):
        async with RobinhoodClient(timeout=pytest.TIMEOUT) as client:
            client._session = None
