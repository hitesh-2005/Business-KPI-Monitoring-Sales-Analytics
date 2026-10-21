"""
KPI Engine — Automated Business KPI Monitoring & Sales Analytics Platform
=============================================================================
Executes analytical SQL models (Recursive CTEs, Window Functions, LAG) directly
against the SQLite warehouse to build a continuous, mathematically bounded daily KPI
time series, regional weekly rollups, category margins, and product rankings.

Execution:
    python analytics/kpi_engine.py
"""

import logging
import os
import sqlite3
import sys

import pandas as pd

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, BASE_DIR, LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | KPI | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "kpi.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def load_sql_queries() -> dict[str, str]:
    """Parse queries from sql/kpi_queries.sql by query name tag."""
    sql_file = os.path.join(BASE_DIR, "sql", "kpi_queries.sql")
    if not os.path.exists(sql_file):
        raise FileNotFoundError(f"SQL queries file not found: {sql_file}")

    with open(sql_file, "r", encoding="utf-8") as f:
        content = f.read()

    queries = {}
    sections = content.split("-- Query Name: ")
    for sec in sections[1:]:
        lines = sec.strip().split("\n")
        q_name = lines[0].strip()
        q_body = "\n".join(lines[1:]).strip().rstrip(";")
        queries[q_name] = q_body

    return queries


def execute_daily_kpis_sql(db_path: str = DB_PATH, queries: dict = None) -> pd.DataFrame:
    """Execute continuous calendar CTE & window functions to build daily KPIs."""
    if queries is None:
        queries = load_sql_queries()

    query = queries.get("POPULATE_DAILY_KPIS")
    if not query:
        raise ValueError("POPULATE_DAILY_KPIS query definition not found in kpi_queries.sql")

    with sqlite3.connect(db_path) as conn:
        daily_df = pd.read_sql_query(query, conn, parse_dates=["kpi_date"])

        # Persist into kpi_daily table in SQLite
        conn.execute("DELETE FROM kpi_daily")
        df_to_save = daily_df.copy()
        df_to_save["kpi_date"] = df_to_save["kpi_date"].dt.strftime("%Y-%m-%d")
        df_to_save.to_sql("kpi_daily", conn, if_exists="append", index=False)
        conn.commit()

    log.info(f"Persisted {len(daily_df):,} continuous calendar daily records into kpi_daily table")
    return daily_df


def execute_regional_weekly_sql(db_path: str = DB_PATH, queries: dict = None) -> pd.DataFrame:
    """Execute weekly regional aggregation with lag window functions and partial week flags."""
    if queries is None:
        queries = load_sql_queries()

    query = queries.get("GET_REGION_WEEKLY")
    with sqlite3.connect(db_path) as conn:
        region_df = pd.read_sql_query(query, conn, parse_dates=["week", "week_end"])

    log.info(f"Loaded {len(region_df):,} regional weekly records with WoW lag metrics")
    return region_df


def execute_category_sql(db_path: str = DB_PATH, queries: dict = None) -> pd.DataFrame:
    """Execute category performance with profit margins and revenue share."""
    if queries is None:
        queries = load_sql_queries()

    query = queries.get("GET_CATEGORY_BREAKDOWN")
    with sqlite3.connect(db_path) as conn:
        cat_df = pd.read_sql_query(query, conn)

    log.info(f"Computed category breakdown for {len(cat_df)} categories")
    return cat_df


def execute_top_products_sql(db_path: str = DB_PATH, top_n: int = 10, queries: dict = None) -> pd.DataFrame:
    """Execute top products ranking using DENSE_RANK() window function."""
    if queries is None:
        queries = load_sql_queries()

    query = queries.get("GET_TOP_PRODUCTS")
    with sqlite3.connect(db_path) as conn:
        prod_df = pd.read_sql_query(query, conn, params={"top_n": top_n})

    log.info(f"Retrieved top {len(prod_df)} products by revenue rank")
    return prod_df


def execute_segment_sql(db_path: str = DB_PATH, queries: dict = None) -> pd.DataFrame:
    """Execute customer segment performance aggregation."""
    if queries is None:
        queries = load_sql_queries()

    query = queries.get("GET_SEGMENT_BREAKDOWN")
    with sqlite3.connect(db_path) as conn:
        seg_df = pd.read_sql_query(query, conn)

    return seg_df


def execute_global_summary_sql(db_path: str = DB_PATH, queries: dict = None) -> dict:
    """Execute macro dataset summary metrics over the complete reporting window."""
    if queries is None:
        queries = load_sql_queries()

    query = queries.get("GET_GLOBAL_SUMMARY")
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        row = cur.execute(query).fetchone()
        cols = [c[0] for c in cur.description]

    summary = dict(zip(cols, row))
    log.info(
        f"Global Summary: ${summary['total_revenue']:,.2f} Revenue, "
        f"${summary['total_profit']:,.2f} Profit, {summary['total_orders']:,} Orders, "
        f"{summary['avg_return_rate']:.2f}% Return Rate"
    )
    return summary


def run_kpi_engine(db_path: str = DB_PATH) -> dict:
    """Run full analytical SQL KPI engine and return all reporting datasets."""
    log.info("Starting KPI Engine analytical SQL execution")
    queries = load_sql_queries()

    daily = execute_daily_kpis_sql(db_path, queries)
    regions = execute_regional_weekly_sql(db_path, queries)
    categories = execute_category_sql(db_path, queries)
    products = execute_top_products_sql(db_path, top_n=10, queries=queries)
    segments = execute_segment_sql(db_path, queries)
    summary = execute_global_summary_sql(db_path, queries)

    log.info("KPI Engine execution completed successfully")
    return {
        "daily": daily,
        "regions": regions,
        "categories": categories,
        "products": products,
        "segments": segments,
        "summary": summary,
    }


if __name__ == "__main__":
    results = run_kpi_engine()
    print("\nSample Continuous Daily KPIs (Latest 5):")
    print(results["daily"].tail(5)[["kpi_date", "revenue", "profit", "orders", "order_return_rate", "revenue_7d_avg", "revenue_wow_pct"]].to_string(index=False))
