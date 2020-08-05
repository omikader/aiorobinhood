import enum


class ChallengeType(enum.Enum):
    """An :class:`~.enum.Enum` for the challenge delivery method.

    Attributes:
        EMAIL
        SMS
    """

    EMAIL = "email"
    SMS = "sms"


class HistoricalInterval(enum.Enum):
    """An :class:`~.enum.Enum` for the interval step size for historical queries.

    Attributes:
        FIVE_MIN
        TEN_MIN
        HOUR
        DAY
        WEEK
    """

    FIVE_MIN = "5minute"
    TEN_MIN = "10minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


class HistoricalSpan(enum.Enum):
    """An :class:`~.enum.Enum` for the window size for historical queries.

    Attributes:
        DAY
        WEEK
        MONTH
        THREE_MONTH
        YEAR
        FIVE_YEAR
    """

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    THREE_MONTH = "3month"
    YEAR = "year"
    FIVE_YEAR = "5year"


class OrderTimeInForce(enum.Enum):
    """An :class:`~.enum.Enum` for describing the order lifetime.

    Attributes:
        GFD: "good for day"
        GTC: "good 'til canceled"
    """

    GFD = "gfd"
    GTC = "gtc"
