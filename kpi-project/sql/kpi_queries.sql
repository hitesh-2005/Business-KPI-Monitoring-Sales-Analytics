-- =====================================================================
-- Automated Business KPI Monitoring & Sales Analytics Platform
-- Production Analytical SQL Queries & Window Functions
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. CONTINUOUS DAILY KPI CALENDAR & ROLLING WINDOW METRICS
-- Generates a gapless daily time series covering min to max order dates.
-- Handles weekend/holiday gaps by zero-filling missing transaction days,
-- ensuring 7-day rolling averages and WoW lags represent true calendar time.
-- ---------------------------------------------------------------------
-- Query Name: POPULATE_DAILY_KPIS
WITH RECURSIVE calendar(dt) AS (
    SELECT MIN(order_date) FROM fact_sales
    UNION ALL
    SELECT date(dt, '+1 day')
    FROM calendar
    WHERE dt < (SELECT MAX(order_date) FROM fact_sales)
),
daily_agg AS (
    SELECT
        order_date,
        ROUND(SUM(sales), 2) AS revenue,
        ROUND(SUM(profit), 2) AS profit,
        COUNT(DISTINCT order_id) AS orders,
        SUM(quantity) AS units_sold,
        COUNT(DISTINCT CASE WHEN is_returned = 1 THEN order_id END) AS returned_orders,
        SUM(is_returned) AS returned_items,
        CASE
            WHEN SUM(sales) > 0
            THEN ROUND(SUM(sales * discount) / SUM(sales) * 100.0, 2)
            ELSE 0.0
        END AS weighted_discount
    FROM fact_sales
    GROUP BY order_date
),
calendar_daily AS (
    SELECT
        c.dt AS kpi_date,
        COALESCE(d.revenue, 0.0) AS revenue,
        COALESCE(d.profit, 0.0) AS profit,
        CASE
            WHEN COALESCE(d.revenue, 0.0) > 0
            THEN ROUND(d.profit * 100.0 / d.revenue, 2)
            ELSE 0.0
        END AS profit_margin_pct,
        COALESCE(d.orders, 0) AS orders,
        COALESCE(d.units_sold, 0) AS units_sold,
        COALESCE(d.returned_orders, 0) AS returned_orders,
        CASE
            WHEN COALESCE(d.orders, 0) > 0
            THEN ROUND(CAST(d.returned_orders AS REAL) * 100.0 / d.orders, 2)
            ELSE 0.0
        END AS order_return_rate,
        COALESCE(d.returned_items, 0) AS returned_items,
        COALESCE(d.weighted_discount, 0.0) AS weighted_discount,
        CASE WHEN d.order_date IS NOT NULL THEN 1 ELSE 0 END AS is_active_day
    FROM calendar c
    LEFT JOIN daily_agg d ON c.dt = d.order_date
)
SELECT
    kpi_date,
    revenue,
    profit,
    profit_margin_pct,
    orders,
    units_sold,
    returned_orders,
    order_return_rate,
    returned_items,
    weighted_discount,
    ROUND(AVG(revenue) OVER (ORDER BY kpi_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS revenue_7d_avg,
    ROUND(AVG(profit) OVER (ORDER BY kpi_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS profit_7d_avg,
    ROUND(AVG(orders) OVER (ORDER BY kpi_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS orders_7d_avg,
    CASE
        WHEN LAG(revenue, 7) OVER (ORDER BY kpi_date) > 0
        THEN ROUND((revenue - LAG(revenue, 7) OVER (ORDER BY kpi_date)) * 100.0 / LAG(revenue, 7) OVER (ORDER BY kpi_date), 2)
        ELSE NULL
    END AS revenue_wow_pct,
    CASE
        WHEN LAG(revenue, 30) OVER (ORDER BY kpi_date) > 0
        THEN ROUND((revenue - LAG(revenue, 30) OVER (ORDER BY kpi_date)) * 100.0 / LAG(revenue, 30) OVER (ORDER BY kpi_date), 2)
        ELSE NULL
    END AS revenue_mom_pct,
    is_active_day
FROM calendar_daily
ORDER BY kpi_date ASC;


-- ---------------------------------------------------------------------
-- 2. REGIONAL WEEKLY PERFORMANCE & WoW GROWTH WITH PARTIAL WEEK HANDLING
-- Partitions by region, orders by week start date, and computes prior week
-- revenue with LAG(). Evaluates whether weeks are partial (< 5 active days)
-- to avoid false-positive drop alerts on truncated period boundaries.
-- ---------------------------------------------------------------------
-- Query Name: GET_REGION_WEEKLY
WITH raw_weekly AS (
    SELECT
        region,
        date(order_date, 'weekday 0', '-6 days') AS week,
        date(order_date, 'weekday 0') AS week_end,
        ROUND(SUM(sales), 2) AS revenue,
        ROUND(SUM(profit), 2) AS profit,
        COUNT(DISTINCT order_id) AS orders,
        COUNT(DISTINCT order_date) AS active_days
    FROM fact_sales
    GROUP BY region, week
),
lagged_weekly AS (
    SELECT
        region,
        week,
        week_end,
        revenue,
        profit,
        orders,
        active_days,
        LAG(revenue, 1) OVER (PARTITION BY region ORDER BY week) AS prev_week_revenue,
        LAG(active_days, 1) OVER (PARTITION BY region ORDER BY week) AS prev_week_active_days,
        CASE WHEN active_days < 5 THEN 1 ELSE 0 END AS is_partial_week
    FROM raw_weekly
)
SELECT
    region,
    week,
    week_end,
    revenue,
    profit,
    orders,
    active_days,
    COALESCE(prev_week_revenue, 0.0) AS prev_week_revenue,
    COALESCE(prev_week_active_days, 0) AS prev_week_active_days,
    is_partial_week,
    CASE
        WHEN is_partial_week = 1 THEN NULL
        WHEN prev_week_revenue > 0 THEN ROUND((revenue - prev_week_revenue) * 100.0 / prev_week_revenue, 2)
        ELSE NULL
    END AS wow_pct,
    CASE
        WHEN prev_week_revenue > 0 AND prev_week_active_days > 0
        THEN ROUND(((revenue / active_days) - (prev_week_revenue / prev_week_active_days)) * 100.0 / (prev_week_revenue / prev_week_active_days), 2)
        ELSE NULL
    END AS normalized_daily_wow_pct
FROM lagged_weekly
ORDER BY region ASC, week ASC;


-- ---------------------------------------------------------------------
-- 3. CATEGORY PERFORMANCE, PROFIT MARGINS & OVERALL REVENUE SHARE
-- Aggregates sales and profits per category, computing margin ratios and
-- total revenue contribution share using window function SUM() OVER ().
-- ---------------------------------------------------------------------
-- Query Name: GET_CATEGORY_BREAKDOWN
SELECT
    category,
    ROUND(SUM(sales), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit,
    ROUND(SUM(profit) * 100.0 / NULLIF(SUM(sales), 0), 2) AS profit_margin_pct,
    COUNT(DISTINCT order_id) AS orders,
    SUM(quantity) AS units_sold,
    ROUND(SUM(sales) * 100.0 / SUM(SUM(sales)) OVER (), 2) AS revenue_share_pct,
    ROUND(COUNT(DISTINCT CASE WHEN is_returned = 1 THEN order_id END) * 100.0 / COUNT(DISTINCT order_id), 2) AS order_return_rate
FROM fact_sales
GROUP BY category
ORDER BY revenue DESC;


-- ---------------------------------------------------------------------
-- 4. TOP PRODUCTS BY REVENUE WITH DENSE_RANK WINDOW FUNCTION
-- Groups products by SKU, computes sales, profit, margin %, and assigns
-- dense rank by total revenue generated.
-- ---------------------------------------------------------------------
-- Query Name: GET_TOP_PRODUCTS
WITH prod_ranked AS (
    SELECT
        product_name,
        category,
        sub_category,
        ROUND(SUM(sales), 2) AS revenue,
        ROUND(SUM(profit), 2) AS profit,
        SUM(quantity) AS units_sold,
        COUNT(DISTINCT order_id) AS orders,
        ROUND(SUM(profit) * 100.0 / NULLIF(SUM(sales), 0), 2) AS profit_margin_pct,
        DENSE_RANK() OVER (ORDER BY SUM(sales) DESC) AS revenue_rank
    FROM fact_sales
    GROUP BY product_name
)
SELECT
    revenue_rank,
    product_name,
    category,
    sub_category,
    revenue,
    profit,
    units_sold,
    orders,
    profit_margin_pct
FROM prod_ranked
WHERE revenue_rank <= :top_n
ORDER BY revenue_rank ASC;


-- ---------------------------------------------------------------------
-- 5. CUSTOMER SEGMENT PERFORMANCE SUMMARY
-- Evaluates sales distribution and Average Order Value (AOV) across
-- Consumer, Corporate, and Home Office customer groups.
-- ---------------------------------------------------------------------
-- Query Name: GET_SEGMENT_BREAKDOWN
SELECT
    segment,
    ROUND(SUM(sales), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit,
    ROUND(SUM(profit) * 100.0 / NULLIF(SUM(sales), 0), 2) AS profit_margin_pct,
    COUNT(DISTINCT order_id) AS orders,
    SUM(quantity) AS units_sold,
    ROUND(SUM(sales) / COUNT(DISTINCT order_id), 2) AS avg_order_value
FROM fact_sales
GROUP BY segment
ORDER BY revenue DESC;


-- ---------------------------------------------------------------------
-- 6. GLOBAL MACRO SUMMARY (FULL MONITORING WINDOW)
-- Computes true distinct orders and global macro metrics over the reporting span.
-- ---------------------------------------------------------------------
-- Query Name: GET_GLOBAL_SUMMARY
SELECT
    ROUND(SUM(sales), 2) AS total_revenue,
    ROUND(SUM(profit), 2) AS total_profit,
    ROUND(SUM(profit) * 100.0 / NULLIF(SUM(sales), 0), 2) AS overall_profit_margin_pct,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(quantity) AS total_units_sold,
    COUNT(DISTINCT CASE WHEN is_returned = 1 THEN order_id END) AS total_returned_orders,
    ROUND(COUNT(DISTINCT CASE WHEN is_returned = 1 THEN order_id END) * 100.0 / COUNT(DISTINCT order_id), 2) AS avg_return_rate,
    MIN(order_date) AS min_date,
    MAX(order_date) AS max_date
FROM fact_sales;
