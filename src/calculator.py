from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


MISSING_METHODS = ("Forward Fill", "Drop")


# --------------------------------------------------
# Weighting strategies
# --------------------------------------------------

class WeightingStrategy(ABC):
    """Base class. Subclasses implement _compute; validation is shared."""

    def weights(self, selected: pd.DataFrame) -> pd.Series:
        w = self._compute(selected)

        if w.isna().any() or (w < 0).any():
            raise ValueError(
                "Weights must be non-negative and defined for every stock."
            )

        if not np.isclose(w.sum(), 1.0):
            raise ValueError(
                f"Index weights must sum to 1. "
                f"Current sum: {w.sum():.6f}"
            )

        return w

    @abstractmethod
    def _compute(self, selected: pd.DataFrame) -> pd.Series:
        """Return raw weights indexed by ticker."""


class EqualWeight(WeightingStrategy):
    """w_i = 1 / N"""

    def _compute(self, selected: pd.DataFrame) -> pd.Series:
        tickers = pd.Index(
            selected["ticker"].tolist(),
            name="ticker"
        )

        return pd.Series(
            1 / len(selected),
            index=tickers
        )


class MarketCapWeight(WeightingStrategy):
    """w_i = Market Cap_i / Total Market Cap"""

    def _compute(self, selected: pd.DataFrame) -> pd.Series:
        cap = pd.to_numeric(
            selected["market_cap"],
            errors="coerce"
        )

        if cap.isna().any():
            raise ValueError(
                "One or more selected stocks have "
                "a missing market_cap value."
            )

        if (cap <= 0).any():
            raise ValueError(
                "Market capitalization must be greater than zero."
            )

        tickers = pd.Index(
            selected["ticker"].tolist(),
            name="ticker"
        )

        return pd.Series(
            (cap / cap.sum()).to_numpy(),
            index=tickers
        )


# To add a new weighting method:
# 1. Create another WeightingStrategy subclass.
# 2. Register it here.

STRATEGIES = {
    "Equal Weight": EqualWeight(),
    "Market Cap": MarketCapWeight(),
}


def calculate_weights(
    stocks: pd.DataFrame,
    selected_tickers: list,
    weighting_method: str
) -> pd.DataFrame:
    """Return a DataFrame with columns ticker and weight."""

    selected = stocks[
        stocks["ticker"].isin(selected_tickers)
    ].copy()

    if selected.empty:
        raise ValueError(
            "At least one stock must be selected."
        )

    strategy = STRATEGIES.get(
        weighting_method
    )

    if strategy is None:
        raise ValueError(
            f"Unknown weighting method: "
            f"{weighting_method}"
        )

    weights = strategy.weights(selected)

    return (
        weights
        .rename("weight")
        .reset_index()
        .sort_values(
            "weight",
            ascending=False
        )
    )


# --------------------------------------------------
# Index calculation
# --------------------------------------------------

def calculate_index(
    prices: pd.DataFrame,
    stocks: pd.DataFrame,
    selected_tickers: list,
    weighting_method: str,
    start_date,
    end_date,
    base_value: float = 100.0,
    missing_method: str = "Forward Fill",
):
    """Build a Price Return Index."""

    # ----------------------------------------------
    # Input validation
    # ----------------------------------------------

    if not selected_tickers:
        raise ValueError(
            "Please select at least one stock."
        )

    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    if start_date >= end_date:
        raise ValueError(
            "Start date must be before end date."
        )

    if base_value <= 0:
        raise ValueError(
            "Base value must be greater than zero."
        )

    if missing_method not in MISSING_METHODS:
        raise ValueError(
            f"Unknown missing data method: "
            f"{missing_method}"
        )

    # ----------------------------------------------
    # Prepare price data
    # ----------------------------------------------

    price_data = prices.copy()

    price_data["date"] = pd.to_datetime(
        price_data["date"],
        errors="coerce"
    )

    price_data["close_price"] = pd.to_numeric(
        price_data["close_price"],
        errors="coerce"
    )

    price_data = price_data[
        price_data["ticker"].isin(selected_tickers)
    ].copy()

    if price_data.empty:
        raise ValueError(
            "No price data exists for the selected stocks."
        )

    # Check for duplicate observations.
    if price_data.duplicated(
        subset=["date", "ticker"]
    ).any():

        raise ValueError(
            "Duplicate (date, ticker) rows found "
            "in the price data."
        )

    # ----------------------------------------------
    # Create FULL price matrix
    # ----------------------------------------------
    #
    # Over here, I have created the matrix using the complete available
    # history, not only the user's selected date range.
    #
    # This is important for Forward Fill:
    #
    # If the first selected date is missing for a stock,
    # pandas can use that stock's last known price before
    # the selected start date.
    #
    # Example:
    #
    # Dec 31 = 100
    # Jan 1  = missing
    # Jan 2  = 102
    #
    # Forward Fill will make:
    #
    # Jan 1 = 100
    #
    # If Jan 1 is the user's selected start date, the
    # selected range still starts on Jan 1.

    full_pivot = (
        price_data
        .pivot(
            index="date",
            columns="ticker",
            values="close_price"
        )
        .reindex(
            columns=selected_tickers
        )
        .sort_index()
    )

    # ----------------------------------------------
    # Select user's date range
    # ----------------------------------------------

    price_pivot = full_pivot.loc[
        start_date:end_date
    ].copy()

    if price_pivot.empty:
        raise ValueError(
            "No price data exists for the selected "
            "stocks and date range."
        )

    # ----------------------------------------------
    # Missing data analysis
    # ----------------------------------------------

    warnings = []

    missing_before = int(
        price_pivot
        .isna()
        .sum()
        .sum()
    )

    missing_by_ticker = (
        price_pivot
        .isna()
        .sum()
        .astype(int)
    )

    missing_date_rows = int(
        price_pivot
        .isna()
        .any(axis=1)
        .sum()
    )

    adjusted_rows = 0
    dropped_rows = 0

    if missing_before > 0:

        affected = (
            missing_by_ticker[
                missing_by_ticker > 0
            ]
        )

        ticker_summary = ", ".join(
            f"{ticker} ({count})"
            for ticker, count
            in affected.items()
        )

        warnings.append(
            f"{missing_before} missing price "
            f"observations detected across "
            f"{len(affected)} stock(s)."
        )

        warnings.append(
            f"Affected stocks: "
            f"{ticker_summary}."
        )

        warnings.append(
            f"{missing_date_rows} trading-date rows "
            "contain at least one missing observation."
        )

        # ------------------------------------------
        # Forward Fill
        # ------------------------------------------

        if missing_method == "Forward Fill":

            # Use the FULL history before selecting
            # the requested date range.
            #
            # This allows a price before start_date to
            # fill a missing value on start_date.

            price_pivot = (
                full_pivot
                .ffill()
                .loc[start_date:end_date]
            )

            remaining = int(
                price_pivot
                .isna()
                .sum()
                .sum()
            )

            adjusted_rows = (
                missing_before - remaining
            )

            warnings.append(
                f"{adjusted_rows} missing price "
                "observations were forward-filled."
            )

            # If values are still missing after the
            # forward fill, they must be at the very
            # beginning of the full dataset because
            # there was no earlier price available.

            if remaining > 0:

                rows_before = len(
                    price_pivot
                )

                price_pivot = (
                    price_pivot
                    .dropna(how="any")
                )

                dropped_rows = (
                    rows_before
                    - len(price_pivot)
                )

                warnings.append(
                    f"{remaining} missing price "
                    "observations remained after "
                    "forward fill."
                )

                warnings.append(
                    f"{dropped_rows} date row(s) were "
                    "dropped because no previous "
                    "price was available."
                )

        # ------------------------------------------
        # Drop
        # ------------------------------------------

        else:

            # Respect the user's choice:
            # no forward filling is performed.

            rows_before = len(
                price_pivot
            )

            price_pivot = (
                price_pivot
                .dropna(how="any")
            )

            dropped_rows = (
                rows_before
                - len(price_pivot)
            )

            warnings.append(
                f"{dropped_rows} trading-date row(s) "
                "were dropped because at least one "
                "selected stock had missing data."
            )

    else:

        warnings.append(
            "No missing price observations detected."
        )

    # ----------------------------------------------
    # Validate remaining data
    # ----------------------------------------------

    if price_pivot.empty:
        raise ValueError(
            "No usable price observations remain "
            "after missing-data handling."
        )

    if len(price_pivot) < 2:
        raise ValueError(
            "At least two trading-date observations "
            "are required to calculate index returns."
        )

    # ----------------------------------------------
    # Stock daily returns
    # ----------------------------------------------
    #
    # pct_change() calculates:
    #
    # P(t) / P(t-1) - 1
    #
    # The first row has no previous observation inside
    # the selected calculation range, so its return is NaN.

    stock_returns = (
        price_pivot
        .pct_change()
    )

    stock_returns.index.name = "date"

    # ----------------------------------------------
    # Weights
    # ----------------------------------------------

    weights = calculate_weights(
        stocks=stocks,
        selected_tickers=selected_tickers,
        weighting_method=weighting_method
    )

    weight_series = (
        weights
        .set_index("ticker")["weight"]
        .reindex(
            stock_returns.columns
        )
    )

    if weight_series.isna().any():

        missing_tickers = (
            weight_series[
                weight_series.isna()
            ]
            .index
            .tolist()
        )

        raise ValueError(
            "Missing weights for: "
            + ", ".join(missing_tickers)
        )

    # ----------------------------------------------
    # Index daily return
    # ----------------------------------------------

    index_daily_returns = (
        stock_returns
        .mul(
            weight_series,
            axis=1
        )
        .sum(
            axis=1,
            min_count=1
        )
    )

    # ----------------------------------------------
    # Index level
    # ----------------------------------------------

    index_levels = pd.Series(
        index=index_daily_returns.index,
        dtype=float
    )

    # First selected trading date = base value.
    index_levels.iloc[0] = base_value

    # Compound returns from the second selected
    # trading date onwards.

    for i in range(
        1,
        len(index_levels)
    ):

        index_levels.iloc[i] = (
            index_levels.iloc[i - 1]
            * (
                1
                + index_daily_returns.iloc[i]
            )
        )

    # ----------------------------------------------
    # Index data
    # ----------------------------------------------

    index_data = pd.DataFrame({
        "date": index_daily_returns.index,
        "index_return": index_daily_returns.values,
        "index_level": index_levels.values
    })

    # ----------------------------------------------
    # Performance statistics
    # ----------------------------------------------

    number_of_days = len(
        index_data
    )

    number_of_return_periods = (
        number_of_days - 1
    )

    ending_level = (
        index_data[
            "index_level"
        ].iloc[-1]
    )

    # ----------------------------------------------
    # Cumulative return
    # ----------------------------------------------

    cumulative_return = (
        ending_level
        / base_value
        - 1
    )

    # ----------------------------------------------
    # Annualised return
    # ----------------------------------------------
    #
    # Uses actual calendar days rather than assuming
    # exactly 252 observations represent one year.

    calendar_days = (
        index_data["date"].iloc[-1]
        - index_data["date"].iloc[0]
    ).days

    if calendar_days > 0:

        annualized_return = (
            (
                ending_level
                / base_value
            )
            ** (
                365.25
                / calendar_days
            )
            - 1
        )

    else:

        annualized_return = np.nan

    # ----------------------------------------------
    # Annualised volatility
    # ----------------------------------------------

    valid_returns = (
        index_data[
            "index_return"
        ]
        .dropna()
    )

    if len(valid_returns) > 1:

        annualized_volatility = (
            valid_returns
            .std(ddof=1)
            * np.sqrt(252)
        )

    else:

        annualized_volatility = np.nan

    # ----------------------------------------------
    # Statistics
    # ----------------------------------------------

    statistics = {

        "cumulative_return":
            cumulative_return,

        "annualized_return":
            annualized_return,

        "annualized_volatility":
            annualized_volatility,

        "number_of_days":
            number_of_days,

        "number_of_return_periods":
            number_of_return_periods,

        "calendar_days":
            calendar_days,

        "missing_before":
            missing_before,

        "missing_by_ticker":
            missing_by_ticker.to_dict(),

        "missing_date_rows":
            missing_date_rows,

        "adjusted_rows":
            adjusted_rows,

        "dropped_rows":
            dropped_rows
    }

    # ----------------------------------------------
    # Return results
    # ----------------------------------------------

    return (
        index_data,
        stock_returns,
        weights,
        statistics,
        warnings
    )
