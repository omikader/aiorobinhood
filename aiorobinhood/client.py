import asyncio
import pickle
from types import TracebackType
from typing import Any, Dict, Iterable, List, Optional, Type, Union
from uuid import uuid4

import aiohttp

from . import models, urls
from .decorators import check_session, check_tokens, mutually_exclusive
from .exceptions import ClientAPIError, ClientRequestError


class RobinhoodClient:
    """An HTTP client for interacting with Robinhood.

    By default, the device token is saved to the `session_file` in order to avoid
    re-triggering the SFA challenge flow upon every :meth:`~.login`. With MFA, a
    passcode will need to be manually supplied every time.

    The access and refresh tokens for a particular session can be saved and reloaded
    to the same file using the :meth:`~.dump` and :meth:`~.load` methods, respectively.

    Args:
        timeout: The request timeout, in seconds.
        session: An open client session to inject, if possible.
        session_file: A path to a binary file for saving session variables.
    """

    _CLIENT_ID: str = "c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS"

    def __init__(
        self,
        timeout: int,
        session: Optional[aiohttp.ClientSession] = None,
        session_file: str = ".aiorobinhood.pickle",
    ) -> None:
        self._timeout = timeout
        self._session = session
        self._session_file = session_file
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._account_url: Optional[str] = None
        self._account_num: Optional[str] = None

        # Load the device token or generate a new one and save it
        with open(self._session_file, "ab+") as f:
            try:
                f.seek(0)
                data = pickle.load(f)
                self._device_token = data["device_token"]
            except EOFError:
                self._device_token = str(uuid4())
                pickle.dump({"device_token": self._device_token}, f)

    async def __aenter__(self) -> "RobinhoodClient":
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    @check_session
    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        assert self._session is not None

        await self._session.close()
        self._session = None

    ###################################################################################
    #                                     OAUTH                                       #
    ###################################################################################

    @check_session
    async def login(
        self,
        username: str,
        password: str,
        expires_in: int = 86400,
        challenge_type: models.ChallengeType = models.ChallengeType.SMS,
        **kwargs,
    ) -> None:
        """Authenticate the user (for both SFA and MFA accounts).

        Args:
            username: The account username.
            password: The account password.
            expires_in: The session duration, in seconds.
            challenge_type: The challenge type (SFA only).

        Raises:
            ClientAPIError: Robinhood servers responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        url = urls.LOGIN

        try:
            async with self._session.post(
                url,
                timeout=self._timeout,
                headers={
                    "x-robinhood-challenge-response-id": kwargs.get("challenge_id", "")
                },
                json={
                    "challenge_type": challenge_type.value,
                    "client_id": self._CLIENT_ID,
                    "device_token": self._device_token,
                    "expires_in": expires_in,
                    "grant_type": "password",
                    "mfa_code": kwargs.get("mfa_code", ""),
                    "password": password,
                    "scope": "internal",
                    "username": username,
                },
            ) as resp:
                response = await resp.json()
                while (
                    "challenge" in response
                    and response["challenge"]["remaining_attempts"] > 0
                ):
                    url = urls.CHALLENGE / response["challenge"]["id"] / "respond/"
                    challenge_id = input(f"Enter the {challenge_type.value} code: ")
                    async with self._session.post(
                        url, timeout=self._timeout, json={"response": challenge_id},
                    ) as resp:
                        response = await resp.json()

                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)
                elif "id" in response:
                    # Try again with challenge_id if challenge is passed
                    return await self.login(
                        username, password, expires_in, challenge_id=response["id"],
                    )
                elif response.get("mfa_required"):
                    # Try again with mfa_code if 2fac is enabled
                    mfa_code = input(f"Enter the {response['mfa_type']} code: ")
                    return await self.login(
                        username, password, expires_in, mfa_code=mfa_code,
                    )
                else:
                    self._access_token = f"Bearer {response['access_token']}"
                    self._refresh_token = response["refresh_token"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("POST", url) from e

        # Fetch the account info during login for other methods
        account = await self.get_account()
        self._account_url = account["url"]
        self._account_num = account["account_number"]

    @check_tokens
    @check_session
    async def logout(self) -> None:
        """Invalidate the current session tokens.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        try:
            async with self._session.post(
                urls.LOGOUT,
                timeout=self._timeout,
                json={"client_id": self._CLIENT_ID, "token": self._refresh_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                self._access_token = None
                self._refresh_token = None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("POST", urls.LOGOUT) from e

    @check_tokens
    @check_session
    async def refresh(self, expires_in: int = 86400) -> None:
        """Fetch a fresh set session tokens.

        Args:
            expires_in: The session duration, in seconds.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        try:
            async with self._session.post(
                urls.LOGIN,
                timeout=self._timeout,
                json={
                    "client_id": self._CLIENT_ID,
                    "expires_in": expires_in,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "scope": "internal",
                },
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                self._access_token = f"Bearer {response['access_token']}"
                self._refresh_token = response["refresh_token"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("POST", urls.LOGIN) from e

    @check_tokens
    async def dump(self) -> None:
        """Write the session tokens to the session file.

        Raises:
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
        """
        with open(self._session_file, "rb+") as f:
            data = pickle.load(f)
            data["access_token"] = self._access_token
            data["refresh_token"] = self._refresh_token
            f.seek(0)
            pickle.dump(data, f)
            f.truncate()

    async def load(self) -> None:
        """Read the session tokens from the session file.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        with open(self._session_file, "rb") as f:
            data = pickle.load(f)
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")

        # Fetch the account URL during login for order methods
        account = await self.get_account()
        self._account_url = account["url"]
        self._account_num = account["account_number"]

    ###################################################################################
    #                                    PROFILE                                      #
    ###################################################################################

    @check_tokens
    @check_session
    async def get_account(self) -> Dict[str, Any]:
        """Fetch information associated with the Robinhood account.

        Returns:
            The account information.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        try:
            async with self._session.get(
                urls.ACCOUNTS,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response["results"][0]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", urls.ACCOUNTS) from e

    @check_tokens
    @check_session
    async def get_portfolio(self) -> Dict[str, Any]:
        """Fetch the portfolio information associated with the Robinhood account.

        Returns:
            The account's portfolio characteristics including equity value, margin,
            and withdrawable amount.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        try:
            async with self._session.get(
                urls.PORTFOLIOS,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response["results"][0]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", urls.PORTFOLIOS) from e

    @check_tokens
    @check_session
    async def get_historical_portfolio(
        self,
        interval: models.HistoricalInterval,
        span: models.HistoricalSpan,
        extended_hours: bool = False,
    ) -> Dict[str, Any]:
        """Fetch the historical value of the account portfolio.

        Args:
            interval: The granularity of the historical data.
            span: The period of the historical data.
            extended_hours: Include data from extended trading hours.

        Returns:
            Historical equity values of the account portfolio over the given interval
            and span.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.

        Warning:
            Certain combinations of ``interval`` and ``span`` will be rejected by
            Robinhood.
        """
        assert self._session is not None

        url = (urls.PORTFOLIOS / "historicals" / f"{self._account_num}/").with_query(
            {
                "bounds": "extended" if extended_hours else "regular",
                "interval": interval.value,
                "span": span.value,
            }
        )

        try:
            async with self._session.get(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", url) from e

    ###################################################################################
    #                                    ACCOUNT                                      #
    ###################################################################################

    @check_tokens
    @check_session
    async def get_positions(
        self, nonzero: bool = True, pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all the positions held by the account.

        Args:
            nonzero: Only fetch open positions.
            pages: The number of pages to fetch (default is unlimited).

        Returns:
            Position data for each holding, including quantity of shares held and
            average buy price.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        results = []
        url = urls.POSITIONS.with_query({"nonzero": str(nonzero).lower()})

        while url is not None and (pages is None or pages > 0):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    headers={"Authorization": self._access_token},
                ) as resp:
                    response = await resp.json()
                    if resp.status != 200:
                        raise ClientAPIError(
                            resp.method, resp.url, resp.status, response
                        )

                    results += response["results"]
                    url = response["next"]
                    pages = pages and pages - 1
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise ClientRequestError("GET", url) from e

        return results

    @check_tokens
    @check_session
    async def get_watchlist(
        self, watchlist: str = "Default", pages: Optional[int] = None
    ) -> List[str]:
        """Fetch the securities in a given watchlist.

        Args:
            watchlist: The name of the watclist.
            pages: The number of pages to fetch (default is unlimited).

        Returns:
            A list of instrument URLs in the watchlist.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        results = []
        url = urls.WATCHLISTS / f"{watchlist}/"

        while url is not None and (pages is None or pages > 0):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    headers={"Authorization": self._access_token},
                ) as resp:
                    response = await resp.json()
                    if resp.status != 200:
                        raise ClientAPIError(
                            resp.method, resp.url, resp.status, response
                        )

                    results += response["results"]
                    url = response["next"]
                    pages = pages and pages - 1
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise ClientRequestError("GET", url) from e

        return [result["instrument"] for result in results]

    @check_tokens
    @check_session
    async def add_to_watchlist(
        self, instrument: str, watchlist: str = "Default"
    ) -> None:
        """Add a security to the given watchlist.

        Args:
            instrument: The instrument URL.
            watchlist: The name of the watchlist.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        url = urls.WATCHLISTS / f"{watchlist}/"

        try:
            async with self._session.post(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
                json={"instrument": instrument},
            ) as resp:
                response = await resp.json()
                if resp.status != 201:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("POST", url) from e

    @check_tokens
    @check_session
    async def remove_from_watchlist(self, id_: str, watchlist: str = "Default") -> None:
        """Remove a security from the given watchlist.

        Args:
            id_: The instrument ID.
            watchlist: The name of the watchlist.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        url = urls.WATCHLISTS / watchlist / f"{id_}/"

        try:
            async with self._session.delete(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 204:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("DELETE", url) from e

    ###################################################################################
    #                                    STOCKS                                       #
    ###################################################################################

    @mutually_exclusive("symbols", "instruments")
    @check_tokens
    @check_session
    async def get_fundamentals(
        self,
        symbols: Optional[Iterable[str]] = None,
        instruments: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch the fundamental information pertaining to a list of securities.

        Args:
            symbols: A sequence of stock symbols.
            instruments: A sequence of instrument URLs.

        Returns:
            Fundamental data for each security, including most recent OHLC prices,
            market capitalization, P/E and P/B ratios, etc.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
            ValueError: Both/neither of ``symbols`` and ``instruments`` are supplied.
        """
        assert self._session is not None

        if symbols is not None:
            url = urls.FUNDAMENTALS.with_query({"symbols": ",".join(symbols)})
        elif instruments is not None:
            url = urls.FUNDAMENTALS.with_query({"instruments": ",".join(instruments)})

        try:
            async with self._session.get(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response["results"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", url) from e

    @mutually_exclusive("symbol", "ids")
    @check_tokens
    @check_session
    async def get_instruments(
        self,
        symbol: Optional[str] = None,
        ids: Optional[Iterable[str]] = None,
        pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch the instrument information pertaining to a list of securities.

        Args:
            symbol: A single stock symbol.
            ids: A sequence of instrument IDs.
            pages: The number of pages to fetch (default is unlimited).

        Returns:
            Instrument data for each security, including ID and various URLs for
            fetching particular information.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
            ValueError: Both/neither of ``symbol`` and ``ids`` are supplied.
        """
        assert self._session is not None

        results = []
        if symbol is not None:
            url = urls.INSTRUMENTS.with_query({"symbol": symbol})
        elif ids is not None:
            url = urls.INSTRUMENTS.with_query({"ids": ",".join(ids)})

        while url is not None and (pages is None or pages > 0):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    headers={"Authorization": self._access_token},
                ) as resp:
                    response = await resp.json()
                    if resp.status != 200:
                        raise ClientAPIError(
                            resp.method, resp.url, resp.status, response
                        )

                    results += response["results"]
                    url = response["next"]
                    pages = pages and pages - 1
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise ClientRequestError("GET", url) from e

        return results

    @check_tokens
    @check_session
    async def get_popularity(
        self, ids: Iterable[str], pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch the popularity information pertaining to a list of securities.

        Args:
            ids: A sequence of instrument IDs.
            pages: The number of pages to fetch (default is unlimited).

        Returns:
            Popularity data for each security, including number of open positions
            held on Robinhood.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        results = []
        url = urls.POPULARITY.with_query({"ids": ",".join(ids)})

        while url is not None and (pages is None or pages > 0):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    headers={"Authorization": self._access_token},
                ) as resp:
                    response = await resp.json()
                    if resp.status != 200:
                        raise ClientAPIError(
                            resp.method, resp.url, resp.status, response
                        )

                    results += response["results"]
                    url = response["next"]
                    pages = pages and pages - 1
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise ClientRequestError("GET", url) from e

        return results

    @mutually_exclusive("symbols", "instruments")
    @check_tokens
    @check_session
    async def get_quotes(
        self,
        symbols: Optional[Iterable[str]] = None,
        instruments: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch the quote information pertaining to a list of securities.

        Args:
            symbols: A sequence of stock symbols.
            instruments: A sequence of instrument URLs.

        Returns:
            Quote data for each security, including ask/bid pricing data (both during
            regular and extended trading hours).

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
            ValueError: Both/neither of ``symbols`` and ``instruments`` are supplied.
        """
        assert self._session is not None

        if symbols is not None:
            url = urls.QUOTES.with_query({"symbols": ",".join(symbols)})
        elif instruments is not None:
            url = urls.QUOTES.with_query({"instruments": ",".join(instruments)})

        try:
            async with self._session.get(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response["results"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", url) from e

    @mutually_exclusive("symbols", "instruments")
    @check_tokens
    @check_session
    async def get_historical_quotes(
        self,
        interval: models.HistoricalInterval,
        span: models.HistoricalSpan,
        extended_hours: bool = False,
        symbols: Optional[Iterable[str]] = None,
        instruments: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical quote information pertaining to a list of securities.

        Args:
            interval: The granularity of the historical data.
            span: The period of the historical data.
            extended_hours: Include data from extended trading hours.
            symbols: A sequence of stock symbols.
            instruments: A sequence of instrument URLs.

        Returns:
            Historical quote data for each security, including OHLC pricing data at
            every interval in the given span.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
            ValueError: Both/neither of ``symbols`` and ``instruments`` are supplied.

        Warning:
            Certain combinations of ``interval`` and ``span`` will be rejected by
            Robinhood.
        """
        assert self._session is not None

        url = urls.HISTORICALS.with_query(
            {
                "bounds": "extended" if extended_hours else "regular",
                "interval": interval.value,
                "span": span.value,
            }
        )
        if symbols is not None:
            url = url.update_query({"symbols": ",".join(symbols)})
        elif instruments is not None:
            url = url.update_query({"instruments": ",".join(instruments)})

        try:
            async with self._session.get(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response["results"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", url) from e

    @check_tokens
    @check_session
    async def get_ratings(
        self, ids: Iterable[str], pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch the buy/sell/hold ratings for a sequence of securities.

        Args:
            ids: A sequence of instrument IDs.
            pages: The number of pages to fetch (default is unlimited).

        Returns:
            A list of analyst ratings for the provided securities.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        results = []
        url = urls.RATINGS.with_query({"ids": ",".join(ids)})

        while url is not None and (pages is None or pages > 0):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    headers={"Authorization": self._access_token},
                ) as resp:
                    response = await resp.json()
                    if resp.status != 200:
                        raise ClientAPIError(
                            resp.method, resp.url, resp.status, response
                        )

                    results += response["results"]
                    url = response.get("next")
                    pages = pages and pages - 1
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise ClientRequestError("GET", url) from e

        return results

    @check_tokens
    @check_session
    async def get_tags(self, id_: str) -> List[str]:
        """Fetch the tags for a particular security.

        Args:
            id_: An instrument ID.

        Returns:
            A list of Robinhood tags for the given security.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        url = urls.TAGS / "instrument" / f"{id_}/"

        try:
            async with self._session.get(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return [tag["slug"] for tag in response["tags"]]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", url) from e

    @check_tokens
    @check_session
    async def get_tag_members(self, tag: str) -> List[str]:
        """Fetch the instruments belonging to a particular tag.

        Args:
            tag: The tag name.

        Returns:
            A list of instruments that match the given tag.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        url = urls.TAGS / "tag" / f"{tag}/"

        try:
            async with self._session.get(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response["instruments"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("GET", url) from e

    ###################################################################################
    #                                    ORDERS                                       #
    ###################################################################################

    @check_tokens
    @check_session
    async def get_orders(
        self, order_id: Optional[str] = None, pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch historical order information.

        Args:
            order_id: The ID of a particular order.
            pages: The number of pages to fetch (default is unlimited).

        Returns:
            Order information for a particular order ID, or every order placed on the
            Robinhood account. Order information includes the price, type, and status
            of the order.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        results = []
        url = urls.ORDERS if order_id is None else urls.ORDERS / f"{order_id}/"

        while url is not None and (pages is None or pages > 0):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    headers={"Authorization": self._access_token},
                ) as resp:
                    response = await resp.json()
                    if resp.status != 200:
                        raise ClientAPIError(
                            resp.method, resp.url, resp.status, response
                        )

                    results += response.get("results", [response])
                    url = response.get("next")
                    pages = pages and pages - 1
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise ClientRequestError("GET", url) from e

        return results

    @check_tokens
    @check_session
    async def cancel_order(self, order_id: str) -> None:
        """Cancel an order.

        Args:
            order_id: The ID of a particular order.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert self._session is not None

        url = urls.ORDERS / order_id / "cancel/"

        try:
            async with self._session.post(
                url,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
            ) as resp:
                response = await resp.json()
                if resp.status != 200:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("POST", url) from e

    @check_tokens
    @check_session
    async def place_order(self, **kwargs) -> str:
        assert self._session is not None

        try:
            async with self._session.post(
                urls.ORDERS,
                timeout=self._timeout,
                headers={"Authorization": self._access_token},
                json={"account": self._account_url, "ref_id": str(uuid4()), **kwargs},
            ) as resp:
                response = await resp.json()
                if resp.status != 201:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response["id"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError("POST", urls.ORDERS) from e

    async def place_limit_buy_order(
        self,
        symbol: str,
        price: Union[int, float],
        quantity: int,
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a limit buy order.

        Args:
            symbol: A stock symbol.
            price: The limit price, in dollars.
            quantity: The quantity of shares to buy.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        instruments = await self.get_instruments(symbol=symbol)
        return await self.place_order(
            extended_hours=extended_hours,
            instrument=instruments[0]["url"],
            price=price,
            quantity=quantity,
            side="buy",
            symbol=symbol,
            time_in_force=time_in_force.value,
            trigger="immediate",
            type="limit",
        )

    async def place_limit_sell_order(
        self,
        symbol: str,
        price: Union[int, float],
        quantity: int,
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a limit sell order.

        Args:
            symbol: A stock symbol.
            price: The limit price, in dollars.
            quantity: The quantity of shares to sell.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        instruments = await self.get_instruments(symbol=symbol)
        return await self.place_order(
            extended_hours=extended_hours,
            instrument=instruments[0]["url"],
            price=price,
            quantity=quantity,
            side="sell",
            symbol=symbol,
            time_in_force=time_in_force.value,
            trigger="immediate",
            type="limit",
        )

    @mutually_exclusive("amount", "quantity")
    async def place_market_buy_order(
        self,
        symbol: str,
        amount: Optional[Union[int, float]] = None,
        quantity: Optional[Union[int, float]] = None,
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a market buy order by quantity of shares or dollar amount.

        Args:
            symbol: A stock symbol.
            amount: The amount to buy, in dollars.
            quantity: The quantity of shares to buy.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
            ValueError: Both/neither of ``amount`` and ``quantity`` are supplied.
        """
        quotes = await self.get_quotes(symbols=[symbol])
        ask_price = float(quotes[0]["ask_price"])

        payload = {
            "extended_hours": extended_hours,
            "instrument": quotes[0]["instrument"],
            "price": ask_price,
            "side": "buy",
            "symbol": symbol,
            "time_in_force": time_in_force.value,
            "trigger": "immediate",
            "type": "market",
        }
        if amount is not None:
            payload["dollar_based_amount"] = {
                "amount": round(amount, 2),
                "currency_code": "USD",
            }
            payload["quantity"] = round(amount / ask_price, 6)
        elif quantity is not None:
            payload["quantity"] = round(quantity, 6)

        return await self.place_order(**payload)

    @mutually_exclusive("amount", "quantity")
    async def place_market_sell_order(
        self,
        symbol: str,
        amount: Optional[Union[int, float]] = None,
        quantity: Optional[Union[int, float]] = None,
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a market sell order by quantity of shares or dollar amount.

        Args:
            symbol: A stock symbol.
            amount: The amount to sell, in dollars.
            quantity: The quantity of shares to sell.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
            ValueError: Both/neither of ``amount`` and ``quantity`` are supplied.
        """
        quotes = await self.get_quotes(symbols=[symbol])
        bid_price = float(quotes[0]["bid_price"])

        payload = {
            "extended_hours": extended_hours,
            "instrument": quotes[0]["instrument"],
            "price": bid_price,
            "side": "sell",
            "symbol": symbol,
            "time_in_force": time_in_force.value,
            "trigger": "immediate",
            "type": "market",
        }
        if amount is not None:
            payload["quantity"] = round(amount / bid_price, 6)
            payload["dollar_based_amount"] = {
                "amount": round(amount, 2),
                "currency_code": "USD",
            }
        elif quantity is not None:
            payload["quantity"] = round(quantity, 6)

        return await self.place_order(**payload)

    async def place_stop_buy_order(
        self,
        symbol: str,
        price: Union[int, float],
        quantity: int,
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a stop buy order.

        Args:
            symbol: A stock symbol.
            price: The stop price, in dollars.
            quantity: The quantity of shares to buy.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        instruments = await self.get_instruments(symbol=symbol)
        return await self.place_order(
            extended_hours=extended_hours,
            instrument=instruments[0]["url"],
            price=price,
            quantity=quantity,
            side="buy",
            stop_price=price,
            symbol=symbol,
            time_in_force=time_in_force.value,
            trigger="stop",
            type="market",
        )

    async def place_stop_sell_order(
        self,
        symbol: str,
        price: Union[int, float],
        quantity: int,
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a stop sell order.

        Args:
            symbol: A stock symbol.
            price: The stop price, in dollars.
            quantity: The quantity of shares to sell.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        instruments = await self.get_instruments(symbol=symbol)
        return await self.place_order(
            extended_hours=extended_hours,
            instrument=instruments[0]["url"],
            quantity=quantity,
            side="sell",
            stop_price=price,
            symbol=symbol,
            time_in_force=time_in_force.value,
            trigger="stop",
            type="market",
        )

    async def place_stop_limit_buy_order(
        self,
        symbol: str,
        price: Union[int, float],
        quantity: int,
        stop_price: Union[int, float],
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a limit buy order triggered at a given stop price.

        Args:
            symbol: A stock symbol.
            price: The limit price, in dollars.
            quantity: The quantity of shares to buy.
            stop_price: The stop price at which to place the limit order, in dollars.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        instruments = await self.get_instruments(symbol=symbol)
        return await self.place_order(
            extended_hours=extended_hours,
            instrument=instruments[0]["url"],
            price=price,
            quantity=quantity,
            side="buy",
            stop_price=stop_price,
            symbol=symbol,
            time_in_force=time_in_force.value,
            trigger="stop",
            type="limit",
        )

    async def place_stop_limit_sell_order(
        self,
        symbol: str,
        price: Union[int, float],
        quantity: int,
        stop_price: Union[int, float],
        time_in_force: models.OrderTimeInForce = models.OrderTimeInForce.GFD,
        extended_hours: bool = False,
    ) -> str:
        """Place a limit sell order triggered at a given stop price.

        Args:
            symbol: A stock symbol.
            price: The limit price, in dollars.
            quantity: The quantity of shares to sell.
            stop_price: The stop price at which to place the limit order, in dollars.
            time_in_force: Indicates how long the order should remain active before it
                           executes or expires.
            extended_hours: The order can be executed in extended trading hours.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        instruments = await self.get_instruments(symbol=symbol)
        return await self.place_order(
            extended_hours=extended_hours,
            instrument=instruments[0]["url"],
            price=price,
            quantity=quantity,
            side="sell",
            stop_price=stop_price,
            symbol=symbol,
            time_in_force=time_in_force.value,
            trigger="stop",
            type="limit",
        )
