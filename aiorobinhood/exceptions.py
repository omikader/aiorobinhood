from typing import Any, Dict, Optional

from yarl import URL


class AIORobinhoodError(Exception):
    """Base class for all aiorobinhood errors."""

    pass


class ClientError(AIORobinhoodError):
    """Base class for all :class:`~.RobinhoodClient` errors. """

    pass


class ClientUninitializedError(ClientError):
    """Indicates the :class:`~.RobinhoodClient` was used before initialization."""

    def __init__(self) -> None:
        msg = "The Robinhood client was not initialized properly.\n"
        super().__init__(msg)


class ClientUnauthenticatedError(ClientError):
    """Indicates the :class:`~.RobinhoodClient` was used before authentication."""

    def __init__(self) -> None:
        msg = (
            "The Robinhood client has not been authenticated properly.\n"
            "Try logging in first."
        )
        super().__init__(msg)


class ClientRequestError(ClientError):
    """Indicates there was an issue contacting the Robinhood servers.

    Args:
        method: The HTTP method.
        url: The URL endpoint.
        msg: The exception message.
    """

    def __init__(self, method: str, url: URL, msg: Optional[str] = None) -> None:
        if msg is None:
            msg = f"An error occurred reaching Robinhood.\nRequest: {method} {url}\n"
        super().__init__(msg)
        self.method = method
        self.url = url


class ClientAPIError(ClientRequestError):
    """Indicates there was an invalid response from the Robinhood servers.

    Args:
        method: The HTTP method.
        url: The URL endpoint.
        status: The HTTP error code.
        response: The Robinhood server's response.
    """

    def __init__(
        self, method: str, url: URL, status: int, response: Dict[str, Any]
    ) -> None:
        msg = (
            f"{method} request to {url} responded with a {status} error.\n"
            f"Full Response: {response}"
        )
        super().__init__(method, url, msg)
        self.status = status
        self.response = response
