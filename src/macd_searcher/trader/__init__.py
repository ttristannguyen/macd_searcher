"""The B3 trading bot (docs/trading_bot.md).

The layers are the same as the rest of the app:

* ``plan`` and ``risk`` are pure. Fires, prices and the ledger state go in. The
  target book, the orders and the alerts come out.
* ``ledger`` is the bot's own SQLite file. It holds each rebalance, target and fill.
* ``__main__`` does the network I/O and the Telegram message, once a day.

The bot is a separate process from the scanner. Thus a trading error cannot stop a
scan, and a scan never places an order (docs/trading_strategy.md §8.4).
"""
