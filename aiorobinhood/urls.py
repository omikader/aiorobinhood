from yarl import URL

BASE = URL("https://api.robinhood.com")

# OAuth
OAUTH = BASE / "oauth2/"
LOGIN = OAUTH / "token/"
LOGOUT = OAUTH / "revoke_token/"
CHALLENGE = BASE / "challenge/"

# Profile
ACCOUNTS = BASE / "accounts/"
PORTFOLIOS = BASE / "portfolios/"

# Account
POSITIONS = BASE / "positions/"
WATCHLISTS = BASE / "watchlists/"

# Stocks
FUNDAMENTALS = BASE / "fundamentals/"
INSTRUMENTS = BASE / "instruments/"
POPULARITY = INSTRUMENTS / "popularity/"
QUOTES = BASE / "quotes/"
HISTORICALS = QUOTES / "historicals/"
MIDLANDS = BASE / "midlands/"
RATINGS = MIDLANDS / "ratings/"
TAGS = MIDLANDS / "tags/"

# Orders
ORDERS = BASE / "orders/"
