# ⚡ Mass Stock Screener

An automated quantitative stock screening system that filters the Indian stock universe (NSE and BSE) to identify high-quality, undervalued investment candidates.

## 🔍 How It Works (Methodology)

This system integrates two distinct institutional-grade models developed in adjacent projects:

1. **Risk-Adjusted Outperformance Filter (Fama-French Model):** 
   Loads 10 years of weekly price data for the entire 4,500+ Indian stock universe. It fits a Fama-French 5-factor regression model (`Mkt-RF`, `SMB`, `HML`, `RMW`, `CMA`, `WML`) to compute each stock's expected return. Only stocks with an **Expected Sharpe Ratio > 1.0** (using a risk-free rate of 6.5%) pass to the next stage.
   
2. **Undervaluation Filter (Random Forest P/E Predictor):** 
   Runs the filtered high-Sharpe candidates through a regularized Random Forest model trained on company-level operating metrics (ROCE, margins, debt, reserves). It predicts the "fair" P/E ratio for each stock. A company is flagged as undervalued if its predicted fair price (predicted P/E × EPS) is **greater than its current trading price** (i.e. valuation upside > 0%).

The screening runs automatically on a monthly schedule, committing the results to a static file `data/screened_stocks.json`. The Streamlit dashboard loads this pre-calculated file instantly, maintaining high performance and avoiding Yahoo Finance API rate limits.

---

## 📂 Directory Structure

For automated execution (locally and on GitHub Actions), repositories must be organized side-by-side:

```
Investments/
├── factoranalysis/          # Fama-French Factor model project
│   └── data/
│       ├── nse_map.csv
│       ├── bse_map.csv
│       └── screener_data.db
├── Valuation/               # Random Forest Valuation model project
│   ├── pe_prediction_model.pkl
│   └── indian_stocks_tickers.csv
└── Mass Screening/          # This repository
    ├── data/
    │   └── screened_stocks.json  # Pre-calculated results
    ├── app.py               # Streamlit Dashboard UI
    ├── run_screener.py      # Screening calculation pipeline script
    └── requirements.txt
```

---

## 🛠️ Local Setup & Execution

### 1. Install Dependencies
Ensure you have Python 3.11 installed. From the `Mass Screening` folder, run:
```bash
pip install -r requirements.txt
pip install -r ../factoranalysis/requirements.txt
pip install -r ../Valuation/requirements.txt
```

### 2. Run the Screening Pipeline
To manually run the screening process and update the data file, run:
```bash
python run_screener.py
```
*Note: The script automatically handles deduplication, batches price downloads from Yahoo Finance, copies the populated database, and writes `data/screened_stocks.json` in under 3 minutes.*

### 3. Start the Dashboard
To start the local Streamlit dashboard, run:
```bash
streamlit run app.py
```

---

## 🤖 Automated GitHub Actions Workflow

The automated workflow is defined in `.github/workflows/monthly_screening.yml`.

### Schedule & Process:
* Runs on the **1st of every month at 3:00 AM UTC**.
* Checks out `Mass Screening`, `factoranalysis`, and `valuation` repositories side-by-side.
* Installs dependencies, copies the SQLite database, and runs `run_screener.py`.
* Automatically commits and pushes the updated `data/screened_stocks.json` back to this repository, triggering a redeployment of your live Streamlit Cloud app.

---

## 🌐 Live Deployment (Streamlit Cloud)

1. Push this repository (`Mass Screening`) to your GitHub account (e.g. `https://github.com/dones97/mass-screening`).
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app**, select this repository, select branch `main`, and set the file path to `app.py`.
4. Deploy! Your app will load the static JSON file instantly and stay updated monthly.
