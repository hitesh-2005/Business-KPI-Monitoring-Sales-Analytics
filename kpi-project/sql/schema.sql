-- ============================================================
-- Automated Business KPI Monitoring & Sales Analytics Platform
-- Data Warehouse Schema (PostgreSQL / MySQL / SQLite compatible)
-- ============================================================

DROP TABLE IF EXISTS alert_history;
DROP TABLE IF EXISTS kpi_daily;
DROP TABLE IF EXISTS fact_sales;

-- Cleaned, order-line-level fact table (populated by etl_pipeline.py)
CREATE TABLE fact_sales (
    row_id          INTEGER PRIMARY KEY,
    order_id        TEXT NOT NULL,
    order_date      DATE NOT NULL,
    ship_date       DATE,
    ship_mode       TEXT,
    customer_id     TEXT,
    customer_name   TEXT,
    segment         TEXT,
    city            TEXT,
    state           TEXT,
    country         TEXT,
    region          TEXT,
    category        TEXT,
    sub_category    TEXT,
    product_name    TEXT,
    sales           REAL NOT NULL,
    quantity        INTEGER NOT NULL,
    discount        REAL NOT NULL,
    profit          REAL NOT NULL,
    shipping_cost   REAL DEFAULT 0.0,
    order_priority  TEXT,
    is_returned     INTEGER DEFAULT 0   -- 1 = returned item (deterministic simulation; see README)
);

-- Pre-aggregated continuous daily KPI table (rebuilt by kpi_engine.py using SQL analytics)
CREATE TABLE kpi_daily (
    kpi_date            DATE PRIMARY KEY,
    revenue             REAL NOT NULL DEFAULT 0.0,
    profit              REAL NOT NULL DEFAULT 0.0,
    profit_margin_pct   REAL DEFAULT 0.0,
    orders              INTEGER NOT NULL DEFAULT 0,
    units_sold          INTEGER NOT NULL DEFAULT 0,
    returned_orders     INTEGER NOT NULL DEFAULT 0,
    order_return_rate   REAL DEFAULT 0.0,
    returned_items      INTEGER NOT NULL DEFAULT 0,
    weighted_discount   REAL DEFAULT 0.0,
    revenue_7d_avg      REAL,
    profit_7d_avg       REAL,
    orders_7d_avg       REAL,
    revenue_wow_pct     REAL,
    revenue_mom_pct     REAL,
    is_active_day       INTEGER NOT NULL DEFAULT 1
);

-- Persistent log of all detected threshold breaches and statistical anomalies
CREATE TABLE alert_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    triggered_at    TEXT NOT NULL,
    alert_type      TEXT NOT NULL,      -- REVENUE_DROP, PROFIT_DROP, ORDERS_DROP, RETURN_SPIKE, REGION_ANOMALY, STATISTICAL_ANOMALY
    severity        TEXT NOT NULL,      -- INFO, WARNING, CRITICAL
    metric_value    REAL,
    threshold_value REAL,
    message         TEXT NOT NULL,
    channel_sent    TEXT                -- EMAIL, SLACK, DRY_RUN
);

-- Performance Indexes
CREATE INDEX idx_fact_sales_order_date ON fact_sales(order_date);
CREATE INDEX idx_fact_sales_region ON fact_sales(region);
CREATE INDEX idx_fact_sales_category ON fact_sales(category);
CREATE INDEX idx_fact_sales_order_id ON fact_sales(order_id);
CREATE INDEX idx_kpi_daily_kpi_date ON kpi_daily(kpi_date);
