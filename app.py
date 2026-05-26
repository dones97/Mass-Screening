import streamlit as st
import json
import pandas as pd
import plotly.express as px
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Mass Stock Screener",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Premium Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    /* Global styles */
    .stApp {
        background-color: #0b0f19;
        font-family: 'Outfit', sans-serif;
        color: #f1f5f9;
    }
    
    /* Remove padding around main content */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Header container */
    .header-container {
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 30px 40px;
        margin-bottom: 30px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
        position: relative;
        overflow: hidden;
    }
    
    .header-container::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.12) 0%, transparent 60%);
        pointer-events: none;
    }
    
    .header-title {
        font-size: 2.75rem;
        font-weight: 800;
        background: linear-gradient(90deg, #6366f1, #a855f7, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
        letter-spacing: -0.03em;
    }
    
    .header-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        font-weight: 400;
        margin-bottom: 0px;
    }
    
    /* Glassmorphism Cards */
    .glass-card {
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        padding: 20px;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .glass-card:hover {
        transform: translateY(-3px);
        border-color: rgba(99, 102, 241, 0.25);
        box-shadow: 0 12px 40px 0 rgba(99, 102, 241, 0.15);
    }
    
    .card-value {
        font-size: 2.25rem;
        font-weight: 700;
        margin-bottom: 5px;
        background: linear-gradient(90deg, #a855f7, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .card-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        font-weight: 600;
    }
    
    /* Method Section */
    .method-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        padding: 20px 25px;
        margin-top: 15px;
    }
    
    .method-title {
        font-weight: 600;
        color: #818cf8;
        font-size: 1.1rem;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .method-text {
        font-size: 0.9rem;
        color: #94a3b8;
        line-height: 1.5;
    }
    
    /* Footer */
    .footer {
        margin-top: 50px;
        padding: 25px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        text-align: center;
        font-size: 0.85rem;
        color: #475569;
    }
</style>
""", unsafe_allow_html=True)

# Load JSON Data
@st.cache_data
def load_screened_data():
    try:
        with open("data/screened_stocks.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Error loading screened data: {e}")
        return None

data_dict = load_screened_data()

# 1. Header
st.markdown("""
<div class="header-container">
    <div class="header-title">⚡ Mass Stock Screener</div>
    <div class="header-subtitle">Monthly automated quantitative screening for NSE & BSE universes</div>
</div>
""", unsafe_allow_html=True)

if data_dict is None or not data_dict.get("stocks"):
    st.warning("⚠️ No screened stock data found. Please run the screener pipeline (`run_screener.py`) to generate results.")
    st.stop()

# Parse JSON into DataFrame
stocks_df = pd.DataFrame(data_dict["stocks"])
last_updated = data_dict.get("last_updated", "N/A")

# Pre-format ticker column for links/display
stocks_df['clean_ticker'] = stocks_df['symbol']

# Convert expected return from fraction to percentage
if 'expected_return' in stocks_df.columns:
    stocks_df['expected_return'] = stocks_df['expected_return'] * 100

# 2. Key Metrics Cards Row
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="glass-card">
        <div class="card-value">{len(stocks_df)}</div>
        <div class="card-label">Stocks Screened</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    max_upside = stocks_df['valuation_upside_pct'].max()
    max_upside_ticker = stocks_df.loc[stocks_df['valuation_upside_pct'].idxmax(), 'symbol'] if len(stocks_df) > 0 else "N/A"
    st.markdown(f"""
    <div class="glass-card">
        <div class="card-value">+{max_upside:.1f}% <span style='font-size:1.1rem; color:#64748b; font-weight:400;'>({max_upside_ticker})</span></div>
        <div class="card-label">Highest Valuation Upside</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="card-value" style="font-size: 1.8rem; padding-top: 0.5rem; padding-bottom: 0.4rem;">{last_updated}</div>
        <div class="card-label">Last Updated Date</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

# 3. Main Interface Layout: Filter & Table
st.subheader("📊 Screened Investment Candidates")

# Create Sector and Industry filter in sidebar-like inline options
col_f1, col_f2 = st.columns([1, 3])
with col_f1:
    sectors = ["All"] + sorted(list(stocks_df['sector'].dropna().unique()))
    selected_sector = st.selectbox("Filter by Sector", sectors)

# Filter dataset
filtered_df = stocks_df.copy()
if selected_sector != "All":
    filtered_df = filtered_df[filtered_df['sector'] == selected_sector]

# Sort by default: Valuation Upside descending
filtered_df = filtered_df.sort_values(by='valuation_upside_pct', ascending=False)

# Rearrange columns for display
display_cols = [
    'clean_ticker', 'name', 'sector', 'industry', 'expected_sharpe',
    'expected_return', 'current_price', 'fair_price', 'valuation_upside_pct',
    'market_cap_cr', 'revenue_cagr_3yr', 'npm_avg_3yr', 'price_perf_3yr'
]

display_df = filtered_df[display_cols].copy()

# Render interactive table with premium column styling
st.dataframe(
    display_df,
    column_config={
        "clean_ticker": st.column_config.TextColumn(
            "Ticker",
            help="Stock ticker symbol (excluding suffix)"
        ),
        "name": st.column_config.TextColumn(
            "Company Name",
            width="medium"
        ),
        "sector": st.column_config.TextColumn("Sector"),
        "industry": st.column_config.TextColumn("Industry", width="medium"),
        "expected_sharpe": st.column_config.NumberColumn(
            "Expected Sharpe",
            format="%.2f",
            help="Sharpe ratio predicted by the Fama-French 5-factor OLS model"
        ),
        "expected_return": st.column_config.NumberColumn(
            "Exp. Return (Yr)",
            format="%.1f%%",
            help="Annualized expected return from OLS factors"
        ),
        "current_price": st.column_config.NumberColumn(
            "Price (₹)",
            format="₹%.2f"
        ),
        "fair_price": st.column_config.NumberColumn(
            "Fair Value (₹)",
            format="₹%.2f"
        ),
        "valuation_upside_pct": st.column_config.NumberColumn(
            "Upside (%)",
            format="%.1f%%",
            help="Fair Value upside relative to current price"
        ),
        "market_cap_cr": st.column_config.NumberColumn(
            "Market Cap (Cr.)",
            format="₹%,.0f"
        ),
        "revenue_cagr_3yr": st.column_config.NumberColumn(
            "3yr Rev CAGR",
            format="%.1f%%",
            help="3-year revenue Compound Annual Growth Rate"
        ),
        "npm_avg_3yr": st.column_config.NumberColumn(
            "3yr NPM Avg",
            format="%.1f%%",
            help="3-year average Net Profit Margin"
        ),
        "price_perf_3yr": st.column_config.NumberColumn(
            "3yr Price Perf",
            format="%.1f%%",
            help="3-year historical stock price performance"
        )
    },
    use_container_width=True,
    hide_index=True
)

st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)

# 4. Charts & Visualizations
tab1, tab2 = st.tabs(["📈 Risk vs. Return Analysis", "📊 Top Undervalued Candidates"])

with tab1:
    st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)
    if not filtered_df.empty:
        # Create Scatter Plot
        fig = px.scatter(
            filtered_df,
            x="expected_sharpe",
            y="valuation_upside_pct",
            size="market_cap_cr",
            color="sector",
            hover_name="name",
            hover_data={
                "symbol": True,
                "expected_sharpe": ":.2f",
                "valuation_upside_pct": ":.1f%",
                "expected_return": ":.1f%",
                "market_cap_cr": ":,.0f Cr.",
                "revenue_cagr_3yr": ":.1f%",
                "npm_avg_3yr": ":.1f%"
            },
            labels={
                "expected_sharpe": "Expected Sharpe Ratio (Factor Model)",
                "valuation_upside_pct": "Valuation Upside (%) (RF Model)",
                "sector": "Sector"
            },
            title="Factor Sharpe Ratio vs. Valuation Upside (Size = Market Cap)"
        )
        
        # Style Plotly Dark Theme
        fig.update_layout(
            paper_bgcolor="#0b0f19",
            plot_bgcolor="rgba(30, 41, 59, 0.2)",
            font_color="#94a3b8",
            title_font_size=20,
            title_font_color="#f1f5f9",
            title_font_family="'Outfit', sans-serif",
            xaxis_gridcolor="rgba(255, 255, 255, 0.05)",
            yaxis_gridcolor="rgba(255, 255, 255, 0.05)",
            legend_title_font_color="#f1f5f9"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for charts.")

with tab2:
    st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)
    if not filtered_df.empty:
        # Create Bar Chart
        top_undervalued = filtered_df.sort_values(by="valuation_upside_pct", ascending=False).head(15)
        fig_bar = px.bar(
            top_undervalued,
            x="clean_ticker",
            y="valuation_upside_pct",
            color="expected_sharpe",
            color_continuous_scale="Viridis",
            hover_name="name",
            hover_data={
                "clean_ticker": False,
                "valuation_upside_pct": ":.1f%",
                "expected_sharpe": ":.2f"
            },
            labels={
                "clean_ticker": "Stock Ticker",
                "valuation_upside_pct": "Valuation Upside (%)",
                "expected_sharpe": "Sharpe Ratio"
            },
            title="Top 15 Undervalued Stocks (Color = Expected Sharpe Ratio)"
        )
        
        fig_bar.update_layout(
            paper_bgcolor="#0b0f19",
            plot_bgcolor="rgba(30, 41, 59, 0.2)",
            font_color="#94a3b8",
            title_font_size=20,
            title_font_color="#f1f5f9",
            xaxis_gridcolor="rgba(255, 255, 255, 0.05)",
            yaxis_gridcolor="rgba(255, 255, 255, 0.05)"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No data available for charts.")

# 5. Methodology Overview
st.markdown("""
<div class="method-card">
    <div class="method-title">💡 Screening Methodology & Models</div>
    <div class="method-text">
        This mass stock screener leverages a <b>two-stage quantitative filtration</b> architecture to identify optimal investment candidates:<br>
        <ol style="margin-top: 10px; padding-left: 20px;">
            <li><b>Risk-Adjusted Outperformance Filter (Fama-French Model):</b> Evaluates the entire 4,500+ Indian stock universe by calculating expected returns based on historical exposure (betas) to Fama-French 5 factors. Only stocks with an <b>Expected Sharpe Ratio > 1.0</b> (using weekly returns over a 10-year period and a risk-free rate of 6.5%) are passed.</li>
            <li><b>Undervaluation Filter (Random Forest P/E Prediction Model):</b> Candidates are run through a trained regularized Random Forest regressor that predicts the "fair" P/E ratio based on company-level operating metrics (ROCE, margins, debt, assets). A company is flagged as undervalued if its predicted fair price (predicted P/E × EPS) is <b>greater than its current trading price</b>.</li>
        </ol>
    </div>
</div>
""", unsafe_allow_html=True)

# 6. Footer
st.markdown("""
<div class="footer">
    <p>⚡ Antigravity Stock Screening Engine • Powered by Google Gemini & Python Financial Models</p>
    <p style="font-size: 0.75rem; color: #334155; margin-top: 5px;">This dashboard is updated automatically on the 1st of every month at 3 AM UTC. Local testing only. Not financial advice.</p>
</div>
""", unsafe_allow_html=True)
