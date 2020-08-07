from functools import wraps
from typing import Callable

from .exceptions import ClientUnauthenticatedError, ClientUninitializedError


def check_session(func: Callable):
    @wraps(func)
    async def inner(self, *args, **kwargs):
        if self._session is None:
            raise ClientUninitializedError()
        return await func(self, *args, **kwargs)

    return inner


def check_tokens(func: Callable):
    @wraps(func)
    async def inner(self, *args, **kwargs):
        if self._access_token is None or self._refresh_token is None:
            raise ClientUnauthenticatedError()
        return await func(self, *args, **kwargs)

    return inner


def mutually_exclusive(keyword: str, *keywords: str):
    keywords = (keyword, *keywords)

    def wrapper(func: Callable):
        @wraps(func)
        async def inner(*args, **kwargs):
            if sum(k in keywords for k in kwargs) != 1:
                raise ValueError(f"You must specify exactly one of {keywords}")
            return await func(*args, **kwargs)

        return inner

    return wrapper
