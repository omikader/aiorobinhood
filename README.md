# aiorobinhood
[![build](https://github.com/omikader/aiorobinhood/workflows/build/badge.svg)](https://github.com/omikader/aiorobinhood/actions?query=workflow%3Abuild)
[![codecov](https://codecov.io/gh/omikader/aiorobinhood/branch/master/graph/badge.svg)](https://codecov.io/gh/omikader/aiorobinhood)
[![downloads](https://pepy.tech/badge/aiorobinhood/week)](https://pepy.tech/project/aiorobinhood/week)
[![style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


Thin asynchronous wrapper for the unofficial Robinhood API.

## Why?
- Supports automated trading strategies on Robinhood
- Supports concurrency using asynchronous programming techniques

## Getting Started
```python
import asyncio
import os

from aiorobinhood import RobinhoodClient


username = os.getenv("ROBINHOOD_USERNAME")
password = os.getenv("ROBINHOOD_PASSWORD")

async def main():
    async with RobinhoodClient(timeout=1) as client:
        await client.login(username, password)

        # Buy $10.50 worth of Apple
        await client.place_market_buy_order("AAPL", amount=10.5)

        # End session
        await client.logout()

if __name__ == "__main__":
    asyncio.run(main())
```

## Dependencies
- Python 3.7+
- [aiohttp](https://pypi.org/project/aiohttp/)
- [yarl](https://pypi.org/project/yarl/)

## License
`aiorobinhood` is offered under the MIT license.
