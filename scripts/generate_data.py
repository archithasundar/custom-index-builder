from pathlib import Path

import numpy as np
import pandas as pd


# ==================================================
# PROJECT PATHS
# ==================================================

# This script is expected to be inside src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"

STOCKS_FILE = DATA_DIR / "stocks.csv"
PRICES_FILE = DATA_DIR / "daily_prices.csv"


# ==================================================
# LOAD STOCK UNIVERSE
# ==================================================

if not STOCKS_FILE.exists():
    raise FileNotFoundError(
        f"Stock universe not found: {STOCKS_FILE}"
    )

stocks = pd.read_csv(
    STOCKS_FILE
)


# ==================================================
# VALIDATE STOCK UNIVERSE
# ==================================================

required_columns = {
    "ticker",
    "company_name",
    "sector",
    "market_cap"
}

missing_columns = (
    required_columns
    - set(stocks.columns)
)

if missing_columns:
    raise ValueError(
        "stocks.csv is missing columns: "
        + ", ".join(
            sorted(missing_columns)
        )
    )

if stocks["ticker"].duplicated().any():
    raise ValueError(
        "stocks.csv contains duplicate tickers."
    )

if stocks["ticker"].isna().any():
    raise ValueError(
        "stocks.csv contains missing tickers."
    )


# ==================================================
# GENERATE TRADING DATES
# ==================================================

dates = pd.bdate_range(
    start="2024-01-01",
    end="2026-03-02"
)


# ==================================================
# RANDOM NUMBER GENERATOR
# ==================================================

rng = np.random.default_rng(42)


# ==================================================
# GENERATE PRICE DATA
# ==================================================

records = []

for _, stock in stocks.iterrows():

    ticker = stock["ticker"]

    price = rng.uniform(
        50,
        500
    )

    for date in dates:

        daily_return = rng.normal(
            loc=0.0003,
            scale=0.018
        )

        price = price * (
            1 + daily_return
        )

        price = max(
            price,
            1
        )

        records.append(
            {
                "date": date,
                "ticker": ticker,
                "close_price": round(
                    price,
                    2
                )
            }
        )


prices = pd.DataFrame(
    records
)


# ==================================================
# INJECT SPORADIC MISSING OBSERVATIONS
# ==================================================

all_tickers = stocks[
    "ticker"
].tolist()

shuffled_tickers = rng.permutation(
    all_tickers
)

number_of_sporadic_stocks = max(
    1,
    round(
        len(all_tickers) * 0.20
    )
)

sporadic_tickers = shuffled_tickers[
    :number_of_sporadic_stocks
]

sporadic_missing_count = 0

for ticker in sporadic_tickers:

    ticker_indices = prices.index[
        prices["ticker"] == ticker
    ].to_numpy()

    number_of_missing_days = rng.integers(
        1,
        4
    )

    missing_indices = rng.choice(
        ticker_indices,
        size=min(
            number_of_missing_days,
            len(ticker_indices)
        ),
        replace=False
    )

    prices.loc[
        missing_indices,
        "close_price"
    ] = np.nan

    sporadic_missing_count += len(
        missing_indices
    )


# ==================================================
# INJECT TRADING-HALT MISSING OBSERVATIONS
# ==================================================

remaining_tickers = [
    ticker
    for ticker in all_tickers
    if ticker not in sporadic_tickers
]

number_of_halt_stocks = max(
    1,
    round(
        len(all_tickers) * 0.10
    )
)

halt_tickers = rng.choice(
    remaining_tickers,
    size=min(
        number_of_halt_stocks,
        len(remaining_tickers)
    ),
    replace=False
)

halt_missing_count = 0

for ticker in halt_tickers:

    ticker_indices = prices.index[
        prices["ticker"] == ticker
    ].to_numpy()

    min_start = 10

    max_start = (
        len(ticker_indices) - 10
    )

    if max_start <= min_start:
        continue

    start_position = rng.integers(
        min_start,
        max_start
    )

    block_length = rng.integers(
        3,
        8
    )

    selected_indices = ticker_indices[
        start_position:
        start_position + block_length
    ]

    prices.loc[
        selected_indices,
        "close_price"
    ] = np.nan

    halt_missing_count += len(
        selected_indices
    )


# ==================================================
# SAVE DATA
# ==================================================

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

prices["date"] = prices[
    "date"
].dt.strftime(
    "%Y-%m-%d"
)

prices.to_csv(
    PRICES_FILE,
    index=False
)


# ==================================================
# SUMMARY
# ==================================================

total_missing = int(
    prices["close_price"]
    .isna()
    .sum()
)

print(
    "Data generation complete!"
)

print(
    "Number of stocks:",
    stocks["ticker"].nunique()
)

print(
    "Number of trading days:",
    len(dates)
)

print(
    "Number of price rows:",
    len(prices)
)

print(
    "\nMissing Data Summary"
)

print(
    "Stocks with sporadic glitches:",
    len(sporadic_tickers)
)

print(
    "Stocks with trading halts:",
    len(halt_tickers)
)

print(
    "Sporadic missing observations:",
    sporadic_missing_count
)

print(
    "Trading halt missing observations:",
    halt_missing_count
)

print(
    "Total missing observations:",
    total_missing
)

print(
    "\nSporadic glitch tickers:"
)

print(
    ", ".join(sporadic_tickers)
)

print(
    "\nTrading halt tickers:"
)

print(
    ", ".join(halt_tickers)
)
