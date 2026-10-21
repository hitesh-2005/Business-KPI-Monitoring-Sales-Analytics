# KPI Analytics Pipeline & SQL Warehouse

This directory contains the Python analytics pipeline, SQLite warehouse, statistical models, operational alert engine, and automated test suite for the **Business KPI Monitoring & Sales Analytics Platform**.

For complete project documentation, architecture diagrams, and interactive React dashboard setup, refer to the root [README.md](../README.md).

---

## Directory Architecture

```
kpi-project/
├── requirements.txt               # Minimal Python dependencies (pandas, scikit-learn, statsmodels, pytest)
├── config.py                      # Centralized configuration, thresholds & paths
├── data/
│   ├── superstore_raw.csv         # Raw transactional dataset (9,994 rows)
│   └── warehouse.db               # SQLite database (fact_sales, kpi_daily, alert_history)
├── sql/
│   ├── schema.sql                 # Warehouse DDL schema with indexing
│   └── kpi_queries.sql            # Analytical SQL queries (recursive CTEs, window functions)
├── etl/
│   └── etl_pipeline.py            # Clean, validate, and load CSV to SQLite warehouse
├── analytics/
│   ├── kpi_engine.py              # SQL-driven daily KPI aggregator (1,458 gapless days)
│   ├── anomaly_detection.py       # Z-score & multivariate Isolation Forest models
│   ├── forecasting.py             # Holt-Winters 14-day revenue forecast
│   └── eda_analysis.py            # Standalone CLI execution of exploratory data analysis
├── alerts/
│   └── alert_engine.py            # Rule & anomaly alert evaluator + notification dispatch
├── scheduler/
│   ├── run_pipeline.py            # Master orchestrator: runs all 6 stages & syncs outputs
│   └── cron_setup.md              # Production scheduling reference guide
├── outputs/
│   └── dashboard_data.json        # Pipeline output payload consumed by React frontend
├── logs/                          # Runtime execution logs (.gitkeep)
└── tests/                         # Pytest automated test suite (16 tests)
    ├── conftest.py                # In-memory SQLite test database fixture
    ├── test_kpi_engine.py         # Tests for bounded return rates & calendar continuity
    ├── test_sql_queries.py        # Tests for analytical SQL window functions & rankings
    ├── test_anomaly_and_alerts.py # Tests for model integration & partial-week suppression
    ├── test_forecasting.py        # Tests for 14-day horizon & non-negative revenue bounds
    └── test_data_quality_and_payload.py # Tests for warehouse invariants & JSON schema
```

---

## Pipeline Execution

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the end-to-end pipeline
python scheduler/run_pipeline.py

# 3. Run automated tests
pytest -v

# 4. Run Exploratory Data Analysis (EDA)
python analytics/eda_analysis.py
```
