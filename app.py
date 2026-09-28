import streamlit as st
import pandas as pd
import plotly.express as px

from src.calculator import calculate_index
from src.data_loader import load_data

# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Custom Index Builder",
    page_icon="📈",
    layout="wide"
)


# ==================================================
# LOAD DATA
# ==================================================

@st.cache_data
def get_data():
    return load_data()


try:
    stocks, prices = get_data()

except FileNotFoundError as e:
    st.error(f"Data file not found: {e}")
    st.stop()

except ValueError as e:
    st.error(f"Data validation error: {e}")
    st.stop()

except Exception as e:
    st.error(f"Unable to load data: {e}")
    st.stop()


# ==================================================
# TITLE
# ==================================================

st.title("📈 Custom Index Builder")

st.write(
    """
    Build and analyse a custom Price Return Index
    from a predefined universe of dummy equities.
    """
)


# ==================================================
# SIDEBAR
# ==================================================

with st.sidebar:

    st.header("Index Configuration")

    selected_tickers = st.multiselect(
        "Select Stocks",
        options=stocks["ticker"].tolist(),
        default=stocks["ticker"].tolist()[:5],
        help="Select one or more stocks for the index."
    )

    weighting_method = st.selectbox(
        "Weighting Method",
        [
            "Equal Weight",
            "Market Cap"
        ]
    )

    missing_method = st.selectbox(
        "Missing Price Handling",
        [
            "Forward Fill",
            "Drop"
        ]
    )

    st.divider()

    min_date = prices["date"].min().date()
    max_date = prices["date"].max().date()

    start_date = st.date_input(
        "Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )

    end_date = st.date_input(
        "End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date
    )

    st.divider()

    generate = st.button(
        "Generate Index",
        type="primary",
        use_container_width=True
    )


# ==================================================
# STOCK UNIVERSE
# ==================================================

st.subheader("1. Stock Universe")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Stocks",
    len(stocks)
)

col2.metric(
    "Price Observations",
    len(prices)
)

col3.metric(
    "Available Trading Days",
    prices["date"].nunique()
)

with st.expander("View Stock Universe"):

    st.dataframe(
        stocks,
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# GENERATE INDEX
# ==================================================

if generate:

    if not selected_tickers:
        st.error(
            "Please select at least one stock."
        )
        st.stop()

    if start_date >= end_date:
        st.error(
            "Start date must be before end date."
        )
        st.stop()

    try:

        result = calculate_index(
            prices=prices,
            stocks=stocks,
            selected_tickers=selected_tickers,
            weighting_method=weighting_method,
            start_date=start_date,
            end_date=end_date,
            base_value=100.0,
            missing_method=missing_method
        )

        # Store both the calculation result and
        # the exact configuration used to generate it.

        st.session_state["index_result"] = {
            "result": result,
            "config": {
                "selected_tickers": selected_tickers.copy(),
                "weighting_method": weighting_method,
                "missing_method": missing_method,
                "start_date": start_date,
                "end_date": end_date,
                "base_value": 100.0
            }
        }

    except Exception as e:

        st.error(
            f"Unable to generate index: {e}"
        )
        st.stop()


# ==================================================
# CHECK WHETHER AN INDEX HAS BEEN GENERATED
# ==================================================

if "index_result" not in st.session_state:

    st.info(
        "Configure the index using the sidebar and "
        "click **Generate Index** to begin."
    )

    st.stop()


# ==================================================
# GET CALCULATION RESULTS
# ==================================================

saved_result = st.session_state["index_result"]

(
    index_data,
    stock_returns,
    weights,
    stats,
    warnings
) = saved_result["result"]

result_config = saved_result["config"]

result_selected_tickers = result_config["selected_tickers"]

result_weighting_method = result_config["weighting_method"]

result_missing_method = result_config["missing_method"]

result_start_date = result_config["start_date"]

result_end_date = result_config["end_date"]


# ==================================================
# 2. INDEX SUMMARY
# ==================================================

st.subheader("2. Index Summary")

ending_level = index_data["index_level"].iloc[-1]

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Ending Index Level",
    f"{ending_level:.2f}"
)

col2.metric(
    "Cumulative Return",
    f"{stats['cumulative_return']:.2%}"
)

col3.metric(
    "Annualized Return",
    f"{stats['annualized_return']:.2%}"
)

col4.metric(
    "Annualized Volatility",
    f"{stats['annualized_volatility']:.2%}"
)


# ==================================================
# PRICE RETURN INDEX CHART
# ==================================================

fig = px.line(
    index_data,
    x="date",
    y="index_level",
    title="Custom Price Return Index"
)

fig.update_traces(
    line_width=2
)

fig.update_layout(
    xaxis_title="Date",
    yaxis_title="Index Level",
    hovermode="x unified"
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# ==================================================
# 3. CORE CALCULATIONS
# ==================================================

st.subheader("3. Core Calculations")

st.success(
    "Index successfully generated. "
    "The calculation steps and underlying data are "
    "available below."
)

tab1, tab2, tab3 = st.tabs(
    [
        "Stock Returns",
        "Index Returns",
        "Index Levels"
    ]
)


# ==================================================
# 3.1 STOCK DAILY RETURNS
# ==================================================

with tab1:

    st.markdown("### Stock Daily Returns")

    st.write(
        "The daily return for each selected stock is "
        "calculated using today's closing price relative "
        "to the previous available closing price."
    )

    st.latex(
        r"r_i(t) = \frac{Close_i(t)}{Close_i(t-1)} - 1"
    )

    stock_returns_display = (
        stock_returns
        .reset_index()
        .rename(
            columns={
                "date": "Date"
            }
        )
    )

    for ticker in result_selected_tickers:

        if ticker in stock_returns_display.columns:

            stock_returns_display[ticker] = (
                stock_returns_display[ticker] * 100
            )

    stock_returns_display["Date"] = (
        pd.to_datetime(
            stock_returns_display["Date"]
        ).dt.strftime("%Y-%m-%d")
    )

    st.dataframe(
        stock_returns_display.round(4),
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# 3.2 INDEX DAILY RETURN
# ==================================================

with tab2:

    st.markdown(
        "### Index Daily Return Using Chosen Weights"
    )

    st.write(
        "Each stock return is multiplied by its index "
        "weight. The weighted returns are then summed "
        "to produce the index daily return."
    )

    st.latex(
        r"r_{index}(t) = \sum_i w_i r_i(t)"
    )

    st.write(
        f"**Weighting method:** "
        f"{result_weighting_method}"
    )

    weights_display = weights.copy()

    weights_display["Weight (%)"] = (
        weights_display["weight"] * 100
    )

    weights_display = weights_display[
        ["ticker", "Weight (%)"]
    ]

    weights_display = weights_display.rename(
        columns={
            "ticker": "Stock"
        }
    )

    st.write("**Weights used:**")

    st.dataframe(
        weights_display.round(4),
        use_container_width=True,
        hide_index=True
    )

    index_returns_display = index_data[
        ["date", "index_return"]
    ].copy()

    index_returns_display = (
        index_returns_display.rename(
            columns={
                "date": "Date",
                "index_return": "Index Daily Return (%)"
            }
        )
    )

    index_returns_display[
        "Index Daily Return (%)"
    ] = (
        index_returns_display[
            "Index Daily Return (%)"
        ] * 100
    )

    index_returns_display["Date"] = (
        pd.to_datetime(
            index_returns_display["Date"]
        ).dt.strftime("%Y-%m-%d")
    )

    st.dataframe(
        index_returns_display.round(4),
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# 3.3 INDEX LEVEL
# ==================================================

with tab3:

    st.markdown(
        "### Index Level from Base Value of 100"
    )

    st.write(
        "The index starts at 100. Each subsequent "
        "index return is compounded to calculate "
        "the next index level."
    )

    st.latex(
        r"Level(t) = Level(t-1) \times (1 + r_{index}(t))"
    )

    st.metric(
        "Starting Index Level",
        "100.00"
    )

    index_levels_display = index_data[
        [
            "date",
            "index_return",
            "index_level"
        ]
    ].copy()

    index_levels_display = (
        index_levels_display.rename(
            columns={
                "date": "Date",
                "index_return": "Index Daily Return (%)",
                "index_level": "Index Level"
            }
        )
    )

    index_levels_display[
        "Index Daily Return (%)"
    ] = (
        index_levels_display[
            "Index Daily Return (%)"
        ] * 100
    )

    index_levels_display["Date"] = (
        pd.to_datetime(
            index_levels_display["Date"]
        ).dt.strftime("%Y-%m-%d")
    )

    st.dataframe(
        index_levels_display.round(4),
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# 4. VALIDATION & DATA QUALITY
# ==================================================

st.subheader("4. Validation & Data Quality")

if stats["missing_before"] == 0:

    st.success(
        "✓ No missing price observations were detected."
    )

else:

    for warning in warnings:

        if (
            "Affected stocks" in warning
            or "missing price observations detected" in warning
        ):

            st.warning(
                "⚠ " + warning
            )

        else:

            st.info(
                warning
            )

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Missing Observations",
    stats["missing_before"]
)

col2.metric(
    "Affected Date Rows",
    stats["missing_date_rows"]
)

col3.metric(
    "Values Forward-Filled",
    stats["adjusted_rows"]
)

col4.metric(
    "Rows Dropped",
    stats["dropped_rows"]
)

if stats["missing_before"] > 0:

    missing_by_ticker = pd.DataFrame(
        {
            "Ticker": stats["missing_by_ticker"].keys(),
            "Missing Observations": stats["missing_by_ticker"].values()
        }
    )

    missing_by_ticker = (
        missing_by_ticker[
            missing_by_ticker[
                "Missing Observations"
            ] > 0
        ]
        .sort_values(
            "Missing Observations",
            ascending=False
        )
    )

    st.write(
        "Missing observations by stock:"
    )

    st.dataframe(
        missing_by_ticker,
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# 5. INDEX WEIGHTS
# ==================================================

st.subheader("5. Index Weights")

st.write(
    f"The generated index uses "
    f"{result_weighting_method} weighting."
)

weights_display = weights.copy()

weights_display["Weight (%)"] = (
    weights_display["weight"] * 100
)

weights_display = weights_display.drop(
    columns=["weight"]
)

st.dataframe(
    weights_display.round(4),
    use_container_width=True,
    hide_index=True
)

st.write(
    f"Total weight: "
    f"{weights['weight'].sum():.2%}"
)

weight_chart = px.bar(
    weights_display,
    x="ticker",
    y="Weight (%)",
    title=f"{result_weighting_method} Weights"
)

weight_chart.update_layout(
    xaxis_title="Ticker",
    yaxis_title="Weight (%)"
)

st.plotly_chart(
    weight_chart,
    use_container_width=True
)


# ==================================================
# 6. INDEX DATA
# ==================================================

st.subheader("6. Index Data")

display_data = index_data.copy()

display_data["date"] = (
    pd.to_datetime(display_data["date"])
    .dt.strftime("%Y-%m-%d")
)

display_data["index_return"] = (
    display_data["index_return"] * 100
)

display_data = display_data.rename(
    columns={
        "date": "Date",
        "index_return": "Index Daily Return (%)",
        "index_level": "Index Level"
    }
)

st.dataframe(
    display_data.round(4),
    use_container_width=True,
    hide_index=True
)


# ==================================================
# DOWNLOAD
# ==================================================

csv_data = index_data.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    label="Download Index Data",
    data=csv_data,
    file_name="custom_index.csv",
    mime="text/csv"
)


# ==================================================
# 7. METHODOLOGY
# ==================================================

st.subheader("7. Methodology")

with st.expander("View calculation methodology"):

    st.markdown(
        f"""
        **Index Type:** Price Return Index

        **Base Level:** 100

        **Selected Stocks:** {len(result_selected_tickers)}

        **Weighting:** {result_weighting_method}

        **Missing Data Treatment:** {result_missing_method}

        **Selected Date Range:** {result_start_date} to
        {result_end_date}

        ### 1. Stock Daily Returns

        `r_i(t) = Close_i(t) / Close_i(t-1) - 1`

        ### 2. Index Daily Return

        `r_index(t) = Σ(w_i × r_i(t))`

        ### 3. Index Level

        `Level(t) = Level(t-1) × (1 + r_index(t))`

        ### Equal Weight

        `w_i = 1 / N`

        ### Market Cap Weight

        `w_i = Market Cap_i / Total Market Cap`

        ### Annualized Return

        Annualized return uses the actual calendar
        duration of the selected index period:

        `(Ending Level / Base Level)^(365.25 / Calendar Days) - 1`

        ### Annualized Volatility

        `Daily Return Standard Deviation × √252`

        Dividends are not included because this is a
        **Price Return Index**.
        """
    )


# ==================================================
# 8. GENERATED CONFIGURATION
# ==================================================

st.subheader("8. Generated Configuration")

configuration = pd.DataFrame(
    {
        "Parameter": [
            "Stocks Selected",
            "Weighting Method",
            "Missing Data Method",
            "Start Date",
            "End Date",
            "Base Level",
            "Index Days"
        ],
        "Value": [
            len(result_selected_tickers),
            result_weighting_method,
            result_missing_method,
            str(result_start_date),
            str(result_end_date),
            "100.00",
            stats["number_of_days"]
        ]
    }
)

st.dataframe(
    configuration,
    use_container_width=True,
    hide_index=True
)
