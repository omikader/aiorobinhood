.. _aiorobinhood-client:

======
Client
======

.. currentmodule:: aiorobinhood.client

All communication with the Robinhood servers is done through the
:class:`~.RobinhoodClient`.

.. autoclass:: RobinhoodClient

All :class:`~.RobinhoodClient` request methods call the :meth:`~.request` helper
method below. This method can also be used to craft custom API requests that are not
encapsulated by :class:`~.RobinhoodClient` API methods.

.. automethod:: RobinhoodClient.request

Authentication
==============

.. automethod:: RobinhoodClient.login
.. automethod:: RobinhoodClient.logout
.. automethod:: RobinhoodClient.refresh
.. automethod:: RobinhoodClient.dump
.. automethod:: RobinhoodClient.load

Profile
=======

.. automethod:: RobinhoodClient.get_account
.. automethod:: RobinhoodClient.get_portfolio
.. automethod:: RobinhoodClient.get_historical_portfolio

Account
=======

.. automethod:: RobinhoodClient.get_positions
.. automethod:: RobinhoodClient.get_watchlist
.. automethod:: RobinhoodClient.add_to_watchlist
.. automethod:: RobinhoodClient.remove_from_watchlist

Stocks
======

.. automethod:: RobinhoodClient.get_fundamentals
.. automethod:: RobinhoodClient.get_instruments
.. automethod:: RobinhoodClient.get_quotes
.. automethod:: RobinhoodClient.get_historical_quotes
.. automethod:: RobinhoodClient.get_tags
.. automethod:: RobinhoodClient.get_tag_members

Orders
======

.. automethod:: RobinhoodClient.get_orders
.. automethod:: RobinhoodClient.cancel_order


Placing Orders
--------------

.. warning::
	Robinhood rate limits the ``/orders`` endpoint used by the following methods.

All :class:`~.RobinhoodClient` order methods call the :meth:`~.place_order` helper
method below. This method can also be used to craft custom order requests that are not
encapsulated by :class:`~.RobinhoodClient` order API methods.

.. automethod:: RobinhoodClient.place_order
.. automethod:: RobinhoodClient.place_limit_buy_order
.. automethod:: RobinhoodClient.place_limit_sell_order
.. automethod:: RobinhoodClient.place_market_buy_order
.. automethod:: RobinhoodClient.place_market_sell_order
.. automethod:: RobinhoodClient.place_stop_buy_order
.. automethod:: RobinhoodClient.place_stop_sell_order
.. automethod:: RobinhoodClient.place_stop_limit_buy_order
.. automethod:: RobinhoodClient.place_stop_limit_sell_order
