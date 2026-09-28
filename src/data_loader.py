from pathlib import Path

import pandas as pd


# ==================================================
# PROJECT PATHS
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"

STOCKS_FILE = DATA_DIR / "stocks.csv"
PRICES_FILE = DATA_DIR / "daily_prices.csv"


# ==================================================
# LOAD DATA
# ==================================================

def load_data():
    """
    Load and validate the stock universe and
    daily price data.

    File paths are determined relative to the
    project root so the application does not depend
    on a specific computer or username.

    Missing close prices are allowed because the
    calculator handles them using the user's selected
    missing-data method.
    """

    # ----------------------------------------------
    # Check files exist
    # ----------------------------------------------

    if not STOCKS_FILE.exists():

        raise FileNotFoundError(
            f"Stock data file not found: {STOCKS_FILE}"
        )

    if not PRICES_FILE.exists():

        raise FileNotFoundError(
            f"Price data file not found: {PRICES_FILE}"
        )

    # ----------------------------------------------
    # Read CSV files
    # ----------------------------------------------

    stocks = pd.read_csv(
        STOCKS_FILE
    )

    prices = pd.read_csv(
        PRICES_FILE
    )

    # ----------------------------------------------
    # Required columns
    # ----------------------------------------------

    required_stock_columns = {
        "ticker",
        "company_name",
        "sector",
        "market_cap"
    }

    required_price_columns = {
        "date",
        "ticker",
        "close_price"
    }

    missing_stock_columns = (
        required_stock_columns
        - set(stocks.columns)
    )

    missing_price_columns = (
        required_price_columns
        - set(prices.columns)
    )

    if missing_stock_columns:

        raise ValueError(
            "stocks.csv is missing columns: "
            + ", ".join(
                sorted(missing_stock_columns)
            )
        )

    if missing_price_columns:

        raise ValueError(
            "daily_prices.csv is missing columns: "
            + ", ".join(
                sorted(missing_price_columns)
            )
        )

    # ----------------------------------------------
    # Preserve raw values before conversion
    # ----------------------------------------------
    #
    # This allows us to distinguish:
    #
    #   blank / NaN      -> allowed missing value
    #   "125.50"         -> valid numeric value
    #   "abc"            -> invalid value
    #

    raw_dates = prices["date"].copy()
    raw_prices = prices["close_price"].copy()
    raw_market_caps = stocks["market_cap"].copy()

    # ----------------------------------------------
    # Convert data types
    # ----------------------------------------------

    prices["date"] = pd.to_datetime(
        raw_dates,
        errors="coerce"
    )

    prices["close_price"] = pd.to_numeric(
        raw_prices,
        errors="coerce"
    )

    stocks["market_cap"] = pd.to_numeric(
        raw_market_caps,
        errors="coerce"
    )

    # ----------------------------------------------
    # Validate dates
    # ----------------------------------------------

    if (
        raw_dates.notna()
        & prices["date"].isna()
    ).any():

        raise ValueError(
            "The price data contains invalid dates."
        )

    # ----------------------------------------------
    # Validate stock universe
    # ----------------------------------------------

    if stocks["ticker"].isna().any():

        raise ValueError(
            "The stock universe contains missing tickers."
        )

    if stocks["ticker"].duplicated().any():

        raise ValueError(
            "The stock universe contains duplicate tickers."
        )

    # ----------------------------------------------
    # Validate price tickers
    # ----------------------------------------------

    if prices["ticker"].isna().any():

        raise ValueError(
            "The price data contains missing tickers."
        )

    # ----------------------------------------------
    # Validate price observations
    # ----------------------------------------------

    if prices.duplicated(
        subset=[
            "date",
            "ticker"
        ]
    ).any():

        raise ValueError(
            "The price data contains duplicate "
            "(date, ticker) observations."
        )

    # ----------------------------------------------
    # Validate market cap values
    # ----------------------------------------------

    if (
        raw_market_caps.notna()
        & stocks["market_cap"].isna()
    ).any():

        raise ValueError(
            "The stock universe contains non-numeric "
            "market cap values."
        )

    if stocks["market_cap"].isna().any():

        raise ValueError(
            "The stock universe contains missing "
            "market cap values."
        )

    # ----------------------------------------------
    # Validate close price values
    # ----------------------------------------------
    #
    # Missing close prices are intentionally allowed.
    #
    # Only values that were originally present but
    # could not be converted to numbers are rejected.

    if (
        raw_prices.notna()
        & prices["close_price"].isna()
    ).any():

        raise ValueError(
            "The price data contains non-numeric "
            "close prices."
        )

    # ----------------------------------------------
    # Validate positive values
    # ----------------------------------------------
    #
    # Ignore missing prices here because they are
    # handled later by the calculator.

    if (
        stocks["market_cap"] <= 0
    ).any():

        raise ValueError(
            "Market cap values must be greater than zero."
        )

    if (
        prices["close_price"].dropna() <= 0
    ).any():

        raise ValueError(
            "Close prices must be greater than zero."
        )

    # ----------------------------------------------
    # Validate ticker consistency
    # ----------------------------------------------

    stock_tickers = set(
        stocks["ticker"]
    )

    price_tickers = set(
        prices["ticker"]
    )

    unknown_tickers = (
        price_tickers - stock_tickers
    )

    if unknown_tickers:

        raise ValueError(
            "Price data contains tickers that are not "
            "present in stocks.csv: "
            + ", ".join(
                sorted(unknown_tickers)
            )
        )

    # ----------------------------------------------
    # Sort data
    # ----------------------------------------------

    stocks = stocks.sort_values(
        "ticker"
    ).reset_index(drop=True)

    prices = prices.sort_values(
        ["date", "ticker"]
    ).reset_index(drop=True)

    return stocks, prices
