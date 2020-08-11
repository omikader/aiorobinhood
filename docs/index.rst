.. aiorobinhood documentation master file, created by
   sphinx-quickstart on Tue Jul 14 17:39:36 2020.

========================================
Welcome to aiorobinhood's documentation!
========================================

Asynchronous Robinhood HTTP client built using :mod:`asyncio` and :mod:`aiohttp`.

Getting Started
===============

A simple example using the :class:`~.RobinhoodClient` context manager.

.. code-block:: python

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

Installation
============

*aiorobinhood* can be installed from PyPI.

.. code-block:: bash

    $ pip install aiorobinhood

You can also get the latest code from GitHub.

.. code-block:: bash

    $ pip install git+git://github.com/omikader/aiorobinhood

Dependencies
============

* Python 3.7+
* *aiohttp*
* *yarl*

Table of Contents
=================

.. toctree::
   :name: mastertoc
   :maxdepth: 2

   reference
   misc
