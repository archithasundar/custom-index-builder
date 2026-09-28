# Custom Index Builder

A small web app that builds a custom **Price Return Index** from a universe of 30 dummy stocks. You pick the stocks, a weighting method and a date range, click Generate, and the app shows the index series (base 100), summary metrics and any data quality warnings.

The UI is built with Streamlit. All calculations are written in Python with pandas and NumPy.

## Contents

1. [How to run](#how-to-run)
2. [Project structure](#project-structure)
3. [Architecture](#architecture)
4. [Data format](#data-format)
5. [Price return formula](#price-return-formula)
6. [Weighting methods](#weighting-methods)
7. [Missing data handling](#missing-data-handling)
8. [Validation](#validation)
9. [Assumptions](#assumptions)
10. [Limitations and future improvements](#limitations-and-future-improvements)
11. [Design decisions](#design-decisions)

## How to run

Requires **Python 3.10 to 3.12**.

> **Python version used:** This project was developed and tested with **Python 3.10**.

    git clone https://github.com/<archithasundar>/custom-index-builder.git
    cd custom-index-builder

    python -m venv .venv

    # Windows
    .venv\Scripts\activate

    # macOS / Linux
    source .venv/bin/activate

    pip install -r requirements.txt
    streamlit run app.py

Streamlit opens the app in your browser (usually `http://localhost:8501`).

The two data files are already in `data/`, so the app runs straight away. To regenerate them:

    python scripts/generate_data.py

The generator uses a fixed random seed (`42`), so it produces the same data every time.

## Project structure

```
custom-index-builder/
├── app.py
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   └── calculator.py
├── scripts/
│   └── generate_data.py
├── data/
│   ├── stocks.csv
│   └── daily_prices.csv
├── requirements.txt
└── README.md
```

## Architecture

The project is split into three layers, so each one can change without touching the others.

| Layer | File | Responsibility |
|-------|------|----------------|
| Data | `data/`, `src/data_loader.py`, `scripts/generate_data.py` | Store, generate, load and validate the data |
| Backend (analytics) | `src/calculator.py` | Weights, returns, index levels, statistics, missing data handling |
| UI | `app.py` | Sidebar inputs, calling the calculator, showing results |

**How the UI talks to the backend.** When the user clicks Generate, `app.py` calls `calculate_index(...)` from `src/calculator.py` with the chosen stocks, weighting method, date range and missing data method. The function returns the index data, stock returns, weights, statistics and warnings. `app.py` stores these in `st.session_state` together with the settings that produced them, so the results always match the labels on screen, even if the user later changes the sidebar.

**Why Streamlit.** The brief asks for a web UI with the analytics in Python. Streamlit lets the UI call the Python functions directly, so there is no separate API or JavaScript to maintain. This keeps the project small and easy to explain. The trade-off is that it is less flexible than a full frontend framework and it reruns the script on every interaction (handled with `st.cache_data` for loading and `st.session_state` for results).

**Code organisation.**

- The calculations are plain pandas functions on DataFrames, because they are stateless transformations.
- Weighting uses a small class hierarchy (a strategy pattern). `WeightingStrategy` is an abstract base class with `EqualWeight` and `MarketCapWeight` subclasses. The base class does the shared validation (weights must be non-negative, complete and sum to 1) and each subclass only implements how the raw weights are computed. `calculate_weights` looks the strategy up by name, so it does not need to know which method it is running. To add a method, write one new subclass and register it in `STRATEGIES`.

## Data format

Both files are in `data/`.

**`stocks.csv`** (30 rows, one per stock)

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | text | Unique ID, for example `TECH01` |
| `company_name` | text | Dummy company name |
| `sector` | text | Sector label (6 sectors, 5 stocks each) |
| `market_cap` | number | Dummy market capitalisation, used for market cap weighting |

**`daily_prices.csv`** (one row per stock per business day)

| Column | Type | Description |
|--------|------|-------------|
| `date` | text (`YYYY-MM-DD`) | Business days from 2024-01-01 to 2026-03-02 |
| `ticker` | text | Must exist in `stocks.csv` |
| `close_price` | number | Daily close. Blank means a missing observation |

Prices are simulated as independent random walks (daily return with a mean of 0.03% and a standard deviation of 1.8%). Each stock has a random starting price between 50 and 500.

To test missing data handling, the generator blanks out some prices on purpose:

- about 20% of the stocks get 1 to 3 random missing days (data glitches)
- about 10% of the stocks get one block of 3 to 7 consecutive missing days (trading halts)

## Price return formula

The index is a Price Return Index. It only reflects price changes, with no dividends.

1. Stock daily return:

   `r_i(t) = close_i(t) / close_i(t-1) - 1`

2. Index daily return, using weights `w_i`:

   `r_index(t) = sum over i of (w_i * r_i(t))`

3. Index level, starting from a base value of 100:

   `level(t) = level(t-1) * (1 + r_index(t))`

The index equals 100 on the first date in the selected range, so that date has no return. Returns and compounding start from the second date.

### Summary statistics

- Cumulative return: `ending level / 100 - 1`
- Annualised return: `(ending level / 100) ^ (365.25 / calendar days) - 1`, where calendar days is the number of days between the first and last date
- Annualised volatility: standard deviation of daily index returns (sample, `ddof=1`) multiplied by the square root of 252

## Weighting methods

| Method | Formula | Notes |
|--------|---------|-------|
| Equal Weight | `w_i = 1 / N` | N is the number of selected stocks |
| Market Cap | `w_i = market_cap_i / sum of market_cap of selected stocks` | Market caps are a fixed snapshot from `stocks.csv` |

Both methods are validated the same way: weights must be non-negative, defined for every selected stock, and sum to 1. Market cap weighting also requires a positive `market_cap` for every selected stock.

Weights are held constant over the whole period, as in the brief's formula. In practice this means the index is reset to its target weights every day (daily rebalancing). Weights do not drift with price changes.

## Missing data handling

A missing price is a blank `close_price` for a stock on a date. The user picks one of two methods.

**Forward Fill (default)**

- A missing price is replaced with the stock's most recent available price. The gap day therefore has a 0% return for that stock.
- The fill uses the full price history, not only the selected range. If a stock is missing on the start date, its price from before the start date can be used, so the index still starts on the date the user chose.
- If a stock has no earlier price at all (a gap at the very start of the data), those dates cannot be filled and are dropped, with a warning.

**Drop**

- Any date where at least one selected stock has no price is removed for all stocks.
- The return across a removed date covers several days in one step, because the index goes from the last complete date to the next complete date.

In both cases the app shows:

- the number of missing observations
- which stocks are affected
- how many dates contain a gap
- how many values were forward-filled
- how many dates were dropped

Missing values are counted inside the selected date range only.

## Validation

**When data is loaded (`src/data_loader.py`)**

- Both files exist and have the required columns
- Dates are valid
- Prices are numeric (blanks are allowed and treated as missing; text such as `"abc"` is rejected)
- No duplicate tickers, and no duplicate `(date, ticker)` rows
- Market caps and prices are positive
- Every ticker in the price file exists in the stock universe

**When an index is generated (`src/calculator.py` and `app.py`)**

- At least one stock is selected
- Start date is before end date
- Base value is positive
- The weighting and missing data methods are known
- Price data exists for the chosen stocks and dates
- At least two usable dates remain after missing data handling
- Weights are valid and sum to 1

Errors are shown in the UI as messages, not stack traces.

## Assumptions

- The dates in the data are treated as trading days. There is no holiday calendar.
- Missing prices are data gaps, not real market events, apart from the simulated halts.
- Market cap values are fixed and are not updated with price changes. They are dummy values and are not float-adjusted.
- Weights are constant, which means daily rebalancing.
- The index base date is the first date in the selected range.

## Limitations and future improvements

**Limitations**

- Dummy data only. Prices are independent random walks, so there are no realistic correlations between stocks or sectors.
- Daily rebalancing only. A real index rebalances on a schedule and lets weights drift in between.
- Market cap weights are a static snapshot and are not float-adjusted.
- Only two weighting methods are available in the UI.
- Price return only, with no dividends or total return.
- Data is read from CSV files and everything runs in memory, which is fine for 30 stocks but not for a large universe.
- No automated tests.

**Future improvements**

- Custom weights entered by the user, with a check that they sum to 100%
- Configurable rebalancing (monthly, quarterly) with weights that drift between rebalance dates
- Float-adjusted market caps that update with price
- Automated tests for the formulas and validation, for example a hand-checked two-stock example
- Real market data from a database or API instead of CSV files
- Benchmark comparison and more metrics (maximum drawdown, Sharpe ratio)
- For a larger system: a separate Python API (for example FastAPI) with a dedicated frontend, so the UI and analytics can scale independently

## Design decisions

- **Streamlit for the UI.** The brief asks for a web UI with the analytics in Python. Streamlit calls the Python code directly, so no separate API or JavaScript is needed.
- **Functions for the maths, classes for weighting.** Returns, index levels and statistics are stateless pandas transformations, so plain functions are the simplest fit. Weighting uses a small strategy class hierarchy because it is the one place where new variants are likely, and each variant shares the same validation.
- **Constant weights.** I followed the brief's formula literally, which means daily rebalancing. Weights are not allowed to drift with price changes.
- **Forward Fill uses the full history.** A gap on the start date can use an earlier price, so the index always starts on the date the user selected.
- **Missing data is reported, not hidden.** The UI shows how many values were missing, which stocks were affected and what was done about them.
