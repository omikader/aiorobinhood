import asyncio
import pickle
from types import TracebackType
from typing import Any, Dict, Iterable, List, Optional, Type, Union
from uuid import uuid4

import aiohttp
from yarl import URL

from . import models, urls
from .decorators import check_tokens, mutually_exclusive
from .exceptions import ClientAPIError, ClientRequestError, ClientUninitializedError


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

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self._session is None:
            raise ClientUninitializedError()

        await self._session.close()
        self._session = None

    async def request(
        self,
        method: str,
        url: URL,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        success_code: int = 200,
    ) -> Dict[str, Any]:
        """Make a custom request to the Robinhood API servers.

        Args:
            method: The HTTP request method.
            url: The Robinhood API url.
            json: JSON request parameters.
            headers: HTTP headers to send with the request.
            success_code: The HTTP status code indicating success.

        Returns:
            The JSON response from the Robinhood API servers.

        Raises:
            AssertionError: The origin of the url is not the Robinhood API servers.
            ClientAPIError: Robinhood servers responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        assert url.origin() == urls.BASE
        if self._session is None:
            raise ClientUninitializedError()

        try:
            async with self._session.request(
                method, url, headers=headers, json=json, timeout=self._timeout
            ) as resp:
                response = await resp.json()
                if resp.status != success_code:
                    raise ClientAPIError(resp.method, resp.url, resp.status, response)

                return response
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ClientRequestError(method, url) from e

    ###################################################################################
    #                                      OAUTH                                      #
    ###################################################################################

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
        headers = {"x-robinhood-challenge-response-id": kwargs.get("challenge_id", "")}
        json = {
            "challenge_type": challenge_type.value,
            "client_id": self._CLIENT_ID,
            "device_token": self._device_token,
            "expires_in": expires_in,
            "grant_type": "password",
            "mfa_code": kwargs.get("mfa_code", ""),
            "password": password,
            "scope": "internal",
            "username": username,
        }

        try:
            response = await self.request(
                "POST", urls.LOGIN, headers=headers, json=json
            )
            if response.get("mfa_required"):
                # Try again with mfa_code if 2fac is enabled
                mfa_code = input(f"Enter the {response['mfa_type']} code: ")
                return await self.login(
                    username, password, expires_in, mfa_code=mfa_code
                )
        except ClientAPIError as e:
            response = e.response
            if "challenge" not in response:
                raise e

            while True:
                url = urls.CHALLENGE / response["challenge"]["id"] / "respond/"
                json = {"response": input(f"Enter the {challenge_type.value} code: ")}
                try:
                    response = await self.request("POST", url, json=json)
                    if "id" in response:
                        # Try again with challenge_id if challenge is passed
                        return await self.login(
                            username, password, expires_in, challenge_id=response["id"]
                        )
                except ClientAPIError as e:
                    if e.response["challenge"]["remaining_attempts"] == 0:
                        raise e from None

        self._access_token = f"Bearer {response['access_token']}"
        self._refresh_token = response["refresh_token"]

        # Fetch the account info for other methods
        account = await self.get_account()
        self._account_url = account["url"]
        self._account_num = account["account_number"]

    @check_tokens
    async def logout(self) -> None:
        """Invalidate the current session tokens.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        json = {"client_id": self._CLIENT_ID, "token": self._refresh_token}
        await self.request("POST", urls.LOGOUT, json=json)
        self._access_token = None
        self._refresh_token = None

    @check_tokens
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
        json = {
            "client_id": self._CLIENT_ID,
            "expires_in": expires_in,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "scope": "internal",
        }
        response = await self.request("POST", urls.LOGIN, json=json)
        self._access_token = f"Bearer {response['access_token']}"
        self._refresh_token = response["refresh_token"]

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
    #                                     PROFILE                                     #
    ###################################################################################

    @check_tokens
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
        headers = {"Authorization": self._access_token}
        response = await self.request("GET", urls.ACCOUNTS, headers=headers)
        return response["results"][0]

    @check_tokens
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
        headers = {"Authorization": self._access_token}
        response = await self.request("GET", urls.PORTFOLIOS, headers=headers)
        return response["results"][0]

    @check_tokens
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
        url = (urls.PORTFOLIOS / "historicals" / f"{self._account_num}/").with_query(
            {
                "bounds": "extended" if extended_hours else "regular",
                "interval": interval.value,
                "span": span.value,
            }
        )
        headers = {"Authorization": self._access_token}
        return await self.request("GET", url, headers=headers)

    ###################################################################################
    #                                     ACCOUNT                                     #
    ###################################################################################

    @check_tokens
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
        results = []
        url = urls.POSITIONS.with_query({"nonzero": str(nonzero).lower()})
        headers = {"Authorization": self._access_token}
        while url is not None and (pages is None or pages > 0):
            response = await self.request("GET", URL(url), headers=headers)
            results += response["results"]
            url = response["next"]
            pages = pages and pages - 1

        return results

    @check_tokens
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
        results = []
        url = urls.WATCHLISTS / f"{watchlist}/"
        headers = {"Authorization": self._access_token}
        while url is not None and (pages is None or pages > 0):
            response = await self.request("GET", URL(url), headers=headers)
            results += response["results"]
            url = response["next"]
            pages = pages and pages - 1

        return [result["instrument"] for result in results]

    @check_tokens
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
        url = urls.WATCHLISTS / f"{watchlist}/"
        headers = {"Authorization": self._access_token}
        json = {"instrument": instrument}
        await self.request("POST", url, headers=headers, json=json, success_code=201)

    @check_tokens
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
        url = urls.WATCHLISTS / watchlist / f"{id_}/"
        headers = {"Authorization": self._access_token}
        await self.request("DELETE", url, headers=headers, success_code=204)

    ###################################################################################
    #                                     STOCKS                                      #
    ###################################################################################

    @mutually_exclusive("symbols", "instruments")
    @check_tokens
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
        if symbols is not None:
            url = urls.FUNDAMENTALS.with_query({"symbols": ",".join(symbols)})
        elif instruments is not None:
            url = urls.FUNDAMENTALS.with_query({"instruments": ",".join(instruments)})

        headers = {"Authorization": self._access_token}
        response = await self.request("GET", url, headers=headers)
        return response["results"]

    @mutually_exclusive("symbol", "ids")
    @check_tokens
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
        results = []
        if symbol is not None:
            url = urls.INSTRUMENTS.with_query({"symbol": symbol})
        elif ids is not None:
            url = urls.INSTRUMENTS.with_query({"ids": ",".join(ids)})

        headers = {"Authorization": self._access_token}
        while url is not None and (pages is None or pages > 0):
            response = await self.request("GET", URL(url), headers=headers)
            results += response["results"]
            url = response["next"]
            pages = pages and pages - 1

        return results

    @mutually_exclusive("symbols", "instruments")
    @check_tokens
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
        if symbols is not None:
            url = urls.QUOTES.with_query({"symbols": ",".join(symbols)})
        elif instruments is not None:
            url = urls.QUOTES.with_query({"instruments": ",".join(instruments)})

        headers = {"Authorization": self._access_token}
        response = await self.request("GET", url, headers=headers)
        return response["results"]

    @mutually_exclusive("symbols", "instruments")
    @check_tokens
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

        headers = {"Authorization": self._access_token}
        response = await self.request("GET", url, headers=headers)
        return response["results"]

    @check_tokens
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
        results = []
        url = urls.RATINGS.with_query({"ids": ",".join(ids)})
        headers = {"Authorization": self._access_token}
        while url is not None and (pages is None or pages > 0):
            response = await self.request("GET", URL(url), headers=headers)
            results += response["results"]
            url = response["next"]
            pages = pages and pages - 1

        return results

    @check_tokens
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
        url = urls.TAGS / "instrument" / f"{id_}/"
        headers = {"Authorization": self._access_token}
        response = await self.request("GET", url, headers=headers)
        return [tag["slug"] for tag in response["tags"]]

    @check_tokens
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
        url = urls.TAGS / "tag" / f"{tag}/"
        headers = {"Authorization": self._access_token}
        response = await self.request("GET", url, headers=headers)
        return response["instruments"]

    ###################################################################################
    #                                     ORDERS                                      #
    ###################################################################################

    @check_tokens
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
        results = []
        # fmt: off
        url: Optional[URL] = urls.ORDERS if order_id is None else urls.ORDERS / f"{order_id}/"  # noqa: E501
        # fmt: on
        headers = {"Authorization": self._access_token}
        while url is not None and (pages is None or pages > 0):
            response = await self.request("GET", URL(url), headers=headers)
            results += response.get("results", [response])
            url = response.get("next")
            pages = pages and pages - 1

        return results

    @check_tokens
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
        url = urls.ORDERS / order_id / "cancel/"
        headers = {"Authorization": self._access_token}
        await self.request("POST", url, headers=headers)

    @check_tokens
    async def place_order(self, **kwargs) -> str:
        """Place a custom order.

        Returns:
            The order ID.

        Raises:
            ClientAPIError: Robinhood server responded with an error.
            ClientRequestError: The HTTP request timed out or failed.
            ClientUnauthenticatedError: The :class:`~.RobinhoodClient` is not logged in.
            ClientUninitializedError: The :class:`~.RobinhoodClient` is not initialized.
        """
        headers = {"Authorization": self._access_token}
        json = {"account": self._account_url, "ref_id": str(uuid4()), **kwargs}
        response = await self.request(
            "POST", urls.ORDERS, headers=headers, json=json, success_code=201
        )
        return response["id"]

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
