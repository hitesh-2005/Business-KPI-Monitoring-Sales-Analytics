# Business KPI Monitoring & Sales Analytics Platform

An enterprise-grade, end-to-end analytics engineering and business intelligence project. It ingests raw retail transactional data, models a continuous analytics warehouse using SQL (recursive CTEs, window functions, and LAG logic), detects statistical anomalies with multivariate Isolation Forest and Z-scores, projects 14-day revenue forecasts using Holt-Winters exponential smoothing, evaluates operational thresholds with partial-week false-positive protection, and serves an interactive React/Vite executive dashboard with multi-dimensional filtering.

Designed to demonstrate production-grade Data Analyst, Analytics Engineer, and Business Intelligence skills using reproducible Python, SQLite, and modern React.

---

## Architecture & Data Flow

```
                      Raw CSV Dataset
                 (9,994 retail order lines)
                            │
                            ▼
              ┌───────────────────────────┐
              │       ETL Pipeline        │  etl/etl_pipeline.py
              │  • Schema & type hygiene  │  • Data quality assertions
              │  • Deterministic returns  │  • SQLite loading
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │    Analytical Warehouse   │  sql/schema.sql
              │        (SQLite DB)        │  sql/kpi_queries.sql
              │   fact_sales & kpi_daily  │
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │      SQL KPI Engine       │  analytics/kpi_engine.py
              │  • Recursive calendar CTE │  • Gapless 1,458-day series
              │  • 7-day rolling window   │  • Order-level return rates
              │  • Sales-weighted metrics │  • Market share % OVER()
              └─────────────┬─────────────┘
                            │
                            ▼
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────────────┐             ┌───────────────────┐
│   Anomaly Detection   │             │ Revenue Forecast  │
│ • Rolling Z-scores    │             │ • Holt-Winters ES │
│ • Isolation Forest    │             │ • Non-negative    │
│   (active-day masked) │             │   revenue bounds  │
└───────────┬───────────┘             └─────────┬─────────┘
            │                                   │
            └─────────────────┬─────────────────┘
                              │
                              ▼
              ┌───────────────────────────┐
              │       Alert Engine        │  alerts/alert_engine.py
              │  • Consumes model flags   │  • Partial-week protection
              │  • Threshold comparisons  │  • Dry-run notifications
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │  Dashboard JSON Exporter  │  scheduler/run_pipeline.py
              │   Synced to public asset  │  outputs/dashboard_data.json
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │  React + Vite Dashboard   │  kpi-frontend/
              │  • Dynamic JSON loader    │  • Period/Region/Cat filters
              │  • Recharts visualizations│  • Responsive KPI cards
              └───────────────────────────┘
```

---

## Dataset Scope & Source

- **Dataset**: Superstore Sales Dataset (~10,000 order-line transactions).
- **Scope**: United States nationwide retail sales across 4 geographic regions (West, East, Central, South).
- **Time Span**: 4 full calendar years (January 4, 2011 to December 31, 2014).
- **Entities**: 5,009 unique customer orders across 793 customer accounts and 1,841 unique product SKUs.
- **Granularity**: Line-item transaction level (each row represents an individual SKU within an order).

---

## Core Analytics & Mathematical Definitions

### 1. Gapless Calendar Continuity
Real-world sales data contains non-trading days (weekends, holidays). Calculating rolling metrics or period comparisons using row indices skips calendar days, causing severe metric distortions.
- **Implementation**: A SQLite recursive Common Table Expression (CTE) dynamically builds a complete 1,458-day calendar (`2011-01-04` through `2014-12-31`).
- **Zero-Filling**: Non-trading days are filled with `0.0` for revenue, profit, units, and order counts.
- **Window Functions**: True calendar 7-day rolling averages are calculated via `AVG(revenue) OVER (ORDER BY kpi_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)`.

### 2. Bounded Order-Level Return Rate
- **Problem**: Dividing returned line items by distinct orders yields mathematically invalid return rates (often >100%).
- **Solution**: Evaluated strictly at the distinct order grain:
  $$\text{Order Return Rate} = \frac{\text{Distinct Orders with } \ge 1 \text{ Returned Item}}{\text{Total Distinct Orders in Reporting Period}} \times 100\%$$
- **Mathematical Guarantee**: Strictly bounded between `0.0%` and `100.0%`.

### 3. Sales-Weighted Average Discount
- **Definition**: Unweighted discounts distort portfolio pricing when high discounts occur on low-value items. This platform calculates sales-weighted discount:
  $$\text{Weighted Discount} = \frac{\sum (\text{Discount Rate} \times \text{Gross Sales})}{\sum \text{Gross Sales}}$$

### 4. Partial-Week False-Positive Suppression
- **Problem**: Truncated reporting weeks (e.g., Dec 29–31 containing only 3 trading days) artificially exhibit 70–85% revenue drops when compared to full 7-day prior weeks.
- **Solution**: The weekly aggregation query tracks `active_days` and flags `is_partial_week = 1` for weeks with fewer than 5 active days. The alert engine explicitly suppresses Week-over-Week alerts on partial weeks.

---

## Analytical SQL Engine (`sql/kpi_queries.sql`)

The analytics pipeline executes real analytical SQL against the SQLite warehouse:

1. **Recursive Calendar CTE (`POPULATE_DAILY_KPIS`)**:
   - Generates 1,458 consecutive days using recursive union.
   - Left-joins daily aggregations to preserve date continuity.
   - Computes rolling 7-day averages and prior 7-day lagged metrics using SQL window functions (`ROWS BETWEEN 6 PRECEDING AND CURRENT ROW`, `LAG()`).
2. **Weekly Regional Performance (`GET_REGION_WEEKLY`)**:
   - Aggregates sales and profit by `region` and `strftime('%Y-%W', order_date)`.
   - Computes Week-over-Week percentage change using `LAG(weekly_sales) OVER (PARTITION BY region ORDER BY week)`.
   - Flags incomplete weeks using conditional aggregation: `CASE WHEN COUNT(DISTINCT order_date) < 5 THEN 1 ELSE 0 END`.
3. **Category Breakdown & Margin Analysis (`GET_CATEGORY_BREAKDOWN`)**:
   - Computes Category Profit Margin: `ROUND(SUM(profit) / NULLIF(SUM(sales), 0) * 100.0, 2)`.
   - Computes Category Portfolio Share using unbounded window functions: `ROUND(SUM(sales) / SUM(SUM(sales)) OVER () * 100.0, 2)`.
4. **Product Revenue Rankings (`GET_TOP_PRODUCTS`)**:
   - Ranks top product SKUs by revenue using `DENSE_RANK() OVER (ORDER BY SUM(sales) DESC)`.

---

## Machine Learning & Statistical Models

### 1. Multivariate Anomaly Detection (`analytics/anomaly_detection.py`)
- **Rolling Z-Score**: Computes 30-day rolling Z-scores on daily sales volume:
  $$Z = \frac{x_t - \mu_{30}}{\sigma_{30}}$$
- **Active-Day Masking**: Inactive zero-sales days are masked during rolling statistics calculation to prevent artificially deflating standard deviation and generating false positives.
- **Isolation Forest**: Unsupervised tree ensemble trained on multidimensional features (`revenue`, `profit`, `orders`, `order_return_rate`). Identifies multi-attribute outliers (`contamination=0.03`, `random_state=42`).
- **Alert Integration**: Anomaly flags are directly consumed by the Alert Engine to produce actionable alerts.

### 2. Time-Series Forecasting (`analytics/forecasting.py`)
- **Model**: Holt-Winters Exponential Smoothing with additive weekly seasonality (`seasonal_periods=7`).
- **Horizon**: 14 calendar days into the future.
- **Guardrails**: Fitted strictly on the continuous daily revenue series. Non-negative clipping (`clip(lower=0)`) enforces that revenue forecasts and uncertainty intervals never dip below zero.
- **Fallback**: Includes automated seasonal naive fallback if numerical convergence fails on smaller samples.

---

## Operational Alert Engine (`alerts/alert_engine.py`)

Configurable threshold engine evaluating business KPIs and statistical models:
- **Revenue Drop**: Triggered if latest active day drops >15% below trailing 7-day baseline (Critical if >30%).
- **Profit Drop**: Triggered if latest active day drops >10% below trailing 7-day baseline (Critical if >25%).
- **Order Count Drop**: Triggered if latest active day drops >20% below trailing 7-day baseline.
- **Return Spike**: Triggered if order-level return rate breaches 10% (Critical if >25%).
- **Regional Decline**: Triggered if a completed week drops >25% WoW (partial weeks suppressed).
- **Statistical Anomalies**: Fires when \|Z-score\| > 2.5 or Isolation Forest marks an observation as anomalous.
- **Notification Dispatch**: Dispatches formatted messages via Email (SMTP) and Slack Webhooks. Defaults to safe `DRY_RUN=True` mode with persistent logging to the `alert_history` SQLite table.

---

## Interactive React Dashboard (`kpi-frontend/`)

Modern executive monitoring UI built with **Vite 6, React 19, Tailwind CSS, Lucide Icons, and Recharts**:
- **Dynamic JSON Data Loading**: Fetches real pipeline artifacts from `/dashboard_data.json` with dedicated loading and error states.
- **Interactive Multi-Dimension Filters**:
  - **Time Periods**: `30D` (Trailing Month), `90D` (Quarter), `1Y` (Trailing Year), `2014`, `2013`, and `ALL` (Full History).
  - **Region Selector**: Filter across `All Regions`, `West`, `East`, `Central`, `South`.
  - **Category Selector**: Filter across `All Categories`, `Technology`, `Furniture`, `Office Supplies`.
  - **Dynamic KPI Recalculation**: Executive metric cards (Revenue, Profit, Margin, Orders, Return Rate) recalculate dynamically against selected filters.
- **Visual Analytics**:
  - **Revenue & Profit Trend**: Dual-axis area chart comparing actuals, 7-day rolling averages, and statistical anomaly flags.
  - **14-Day Forecast Projection**: Visualizes forward-looking projections with upper and lower uncertainty bounds.
  - **Regional Performance Cards**: Highlights weekly revenue, WoW growth, and partial-week indicators.
  - **Category Breakdown**: Interactive margin and sales volume distribution.
  - **Top Products Table**: Revenue, margin, and product rankings.
  - **Live Operational Alerts Feed**: Real-time alerts color-coded by severity (`CRITICAL`, `WARNING`).

---

## Repository Structure

```
Business-KPI-Monitoring-Sales-Analytics/
├── README.md                          # Master documentation & project guide
├── .gitignore                         # Git hygiene rules (venv, node_modules, logs, caches)
├── notebooks/
│   └── eda_sales_analysis.ipynb       # Exploratory Data Analysis (EDA) notebook
├── kpi-project/
│   ├── requirements.txt               # Minimal Python dependencies
│   ├── config.py                      # Centralized configuration & thresholds
│   ├── data/
│   │   ├── superstore_raw.csv         # Raw transactional dataset (9,994 rows)
│   │   └── warehouse.db               # SQLite database (fact_sales, kpi_daily, alert_history)
│   ├── sql/
│   │   ├── schema.sql                 # DDL schema with indexing
│   │   └── kpi_queries.sql            # Analytical SQL queries (CTEs, window functions)
│   ├── etl/
│   │   └── etl_pipeline.py            # Clean, validate, and load CSV to SQLite
│   ├── analytics/
│   │   ├── kpi_engine.py              # SQL-driven daily KPI aggregator
│   │   ├── anomaly_detection.py       # Z-score & Isolation Forest models
│   │   ├── forecasting.py             # Holt-Winters 14-day revenue forecast
│   │   └── eda_analysis.py            # Standalone CLI execution of EDA analysis
│   ├── alerts/
│   │   └── alert_engine.py            # Rule & anomaly alert evaluator + dispatch
│   ├── scheduler/
│   │   ├── run_pipeline.py            # Orchestrator: runs all 6 stages & syncs outputs
│   │   └── cron_setup.md              # Production scheduling reference guide
│   ├── outputs/
│   │   └── dashboard_data.json        # Pipeline output payload consumed by UI
│   ├── logs/                          # Runtime execution logs (.gitkeep)
│   └── tests/                         # Pytest automated test suite (16 tests)
│       ├── conftest.py                # In-memory SQLite fixture
│       ├── test_kpi_engine.py         # Tests for bounded return rates & calendar continuity
│       ├── test_sql_queries.py        # Tests for analytical SQL window functions
│       ├── test_anomaly_and_alerts.py # Tests for model integration & partial-week suppression
│       ├── test_forecasting.py        # Tests for 14-day horizon & non-negative bounds
│       └── test_data_quality_and_payload.py # Tests for warehouse invariants & JSON schema
└── kpi-frontend/
    ├── package.json                   # React, Vite, Recharts, Lucide, Tailwind dependencies
    ├── vite.config.js                 # Vite bundler configuration
    ├── public/
    │   └── dashboard_data.json        # Synced production payload
    └── src/
        ├── App.jsx                    # Interactive dashboard component
        ├── main.jsx                   # React 19 entrypoint
        └── index.css                  # Tailwind styles
```

---

## Setup & Execution Guide

### Prerequisites
- **Python**: 3.10+ (tested and verified on Python 3.13)
- **Node.js**: 18+ (tested and verified on Node v24)

### 1. Python Analytics Pipeline Setup

```bash
# Navigate to the backend directory
cd kpi-project

# Install dependencies
pip install -r requirements.txt

# Run the end-to-end analytics pipeline
python scheduler/run_pipeline.py
```

**Pipeline Output**:
```
2026-10-21 13:58:34 | INFO | === Stage 1: ETL Pipeline ===
2026-10-21 13:58:34 | INFO | Loaded 9,994 raw rows. Validated constraints (0 nulls, positive sales/quantities).
2026-10-21 13:58:34 | INFO | === Stage 2: SQL KPI Engine ===
2026-10-21 13:58:35 | INFO | Populated 1,458 gapless daily records into kpi_daily.
2026-10-21 13:58:35 | INFO | === Stage 3: Statistical Anomaly Detection ===
2026-10-21 13:58:35 | INFO | Isolation Forest identified 44 anomalies out of 1,458 days (3.0% contamination).
2026-10-21 13:58:35 | INFO | === Stage 4: Holt-Winters Revenue Forecasting ===
2026-10-21 13:58:36 | INFO | Forecast generated for 14 days (2015-01-01 to 2015-01-14).
2026-10-21 13:58:36 | INFO | === Stage 5: Operational Alert Engine ===
2026-10-21 13:58:36 | INFO | Evaluated thresholds against latest active date 2014-12-31. 4 alerts fired.
2026-10-21 13:58:36 | INFO | === Stage 6: Dashboard Payload Export ===
2026-10-21 13:58:36 | INFO | Successfully synced payload to kpi-frontend/public/dashboard_data.json.
2026-10-21 13:58:36 | INFO | === Pipeline Completed Successfully in 3.21s ===
```

### 2. Run Automated Verification Tests

```bash
# Run the complete test suite from kpi-project/
pytest -v
```

**Verified Test Results**:
```
tests/test_anomaly_and_alerts.py::test_zscore_anomaly_detection PASSED           [  6%]
tests/test_anomaly_and_alerts.py::test_alert_engine_consumes_anomaly_flags PASSED [ 12%]
tests/test_anomaly_and_alerts.py::test_partial_week_suppresses_regional_alert PASSED [ 18%]
tests/test_anomaly_and_alerts.py::test_threshold_revenue_drop_triggers_alert PASSED [ 25%]
tests/test_data_quality_and_payload.py::test_warehouse_data_invariants PASSED   [ 31%]
tests/test_data_quality_and_payload.py::test_dashboard_payload_schema_and_types PASSED [ 37%]
tests/test_forecasting.py::test_forecast_produces_14_days PASSED                 [ 43%]
tests/test_forecasting.py::test_forecast_non_negative_bounds PASSED             [ 50%]
tests/test_forecasting.py::test_forecast_fallback_on_short_series PASSED        [ 56%]
tests/test_kpi_engine.py::test_order_return_rate_bounded_between_0_and_100 PASSED [ 62%]
tests/test_kpi_engine.py::test_calendar_continuity_and_zero_filling PASSED     [ 68%]
tests/test_kpi_engine.py::test_rolling_7d_average_matches_calendar_window PASSED [ 75%]
tests/test_kpi_engine.py::test_weighted_discount_calculation PASSED            [ 81%]
tests/test_sql_queries.py::test_category_breakdown_sql_share_and_margin PASSED  [ 87%]
tests/test_sql_queries.py::test_top_products_dense_rank PASSED                  [ 93%]
tests/test_sql_queries.py::test_global_summary_totals PASSED                   [100%]

============================== 16 passed in 9.31s ==============================
```

### 3. Run Standalone Exploratory Data Analysis (EDA)

```bash
# Execute the documented analytical EDA script
python analytics/eda_analysis.py
```

### 4. React Frontend Setup & Development Server

```bash
# Navigate to the frontend directory
cd ../kpi-frontend

# Install Node dependencies
npm install

# Start Vite local development server
npm run dev
```

Open `http://localhost:5173` in your browser to interact with the executive dashboard.

To verify a production build:
```bash
npm run build
```
*(Verified: Built cleanly in 427ms with 0 errors and 0 warnings).*

---

## Disclosures & Methodological Limitations

1. **Synthetic Return Simulation**: The public Kaggle Superstore sales dataset contains transaction items but does not feature an authentic return status flag. For demonstration of return-rate monitoring, a synthetic `is_returned` flag is generated deterministically in `etl/etl_pipeline.py` (fixed seed `random_state=42`, weighted toward high discounts and negative margins). In production, this would be replaced with an inner join to an authentic ERP/WMS returns table.
2. **Anomaly Detection Context**: The Isolation Forest model and rolling Z-score identify *statistical unusualness*, not proven business failure or confirmed fraud. A sudden volume surge during promotional holidays (e.g., Black Friday / Cyber Monday) registers as statistically anomalous while representing healthy business execution.
3. **Forecasting Uncertainty**: Holt-Winters exponential smoothing intervals provide heuristic projection bands based on historical residual variance; they are not Bayesian credible intervals or formal econometric prediction intervals.

---

## Key Resume Bullet Points

- **End-to-End Analytics Pipeline**: Engineered an automated retail sales KPI monitoring platform ingesting 10K+ transactions into a normalized SQLite warehouse, automating daily aggregation, anomaly detection, forecasting, and executive reporting.
- **Advanced Analytical SQL**: Authored production-grade SQL leveraging recursive calendar CTEs, window functions (`ROWS BETWEEN 6 PRECEDING`), and `LAG()` logic to guarantee 1,458 gapless daily records and eliminate rolling metric distortions caused by non-trading days.
- **Statistical Anomaly & Alert Engine**: Integrated rolling Z-scores and multivariate Isolation Forest models into an operational alert engine featuring partial-week boundary safeguards to prevent false-positive regional drop alerts.
- **Time-Series Forecasting**: Deployed Holt-Winters exponential smoothing with additive weekly seasonality to project 14-day revenue forecasts with non-negative bounds and automated fallback mechanisms.
- **Interactive Modern BI Frontend**: Built a responsive executive dashboard using React 19, Vite, Recharts, and Tailwind CSS, featuring dynamic JSON pipeline consumption and multi-dimensional filtering (Time Period, Region, Category).
- **Quality Assurance**: Designed an automated `pytest` test suite with 16 unit and integration tests covering metric boundary constraints, SQL window functions, JSON schema validation, and warehouse data invariants.

---

## License & Author
- **Author**: Data Analyst & Analytics Engineer
- **License**: MIT License
