"""
ETL Pipeline — Automated Business KPI Monitoring & Sales Analytics Platform
=============================================================================
Extract  : Raw Superstore retail CSV (51,290 records)
Transform: Clean nulls/duplicates, normalize schemas, validate dtypes, filter to US
           commercial scope (9,994 order lines, 2011–2014), engineer simulated return flag
Load     : SQLite warehouse (fact_sales table with indexing)

Execution:
    python etl/etl_pipeline.py
"""

import logging
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

# Add parent directory to sys.path for relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RAW_CSV_PATH, DB_PATH, LOGS_DIR, BASE_DIR

os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | ETL | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "etl.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def extract(csv_path: str = RAW_CSV_PATH) -> pd.DataFrame:
    """Extract raw sales data from CSV file."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Raw dataset not found at expected path: {csv_path}")
    log.info(f"Extracting raw data from {csv_path}")
    df = pd.read_csv(csv_path, encoding="latin-1")
    log.info(f"Extracted {len(df):,} rows, {df.shape[1]} columns")
    return df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Transform, clean, and standardize the raw retail dataset."""
    log.info("Starting transform stage")
    df = df.copy()

    # 1. Standardize column names -> snake_case
    df.columns = [c.strip().lower().replace("-", "_").replace(" ", "_") for c in df.columns]

    # 2. Parse date fields handling mixed day-first / month-first formats safely
    df["order_date"] = pd.to_datetime(df["order_date"], format="mixed", dayfirst=True, errors="coerce")
    df["ship_date"] = pd.to_datetime(df["ship_date"], format="mixed", dayfirst=True, errors="coerce")

    # 3. Clean invalid rows with missing critical keys
    before_drop = len(df)
    df = df.dropna(subset=["order_date", "order_id", "sales"])
    dropped_keys = before_drop - len(df)
    if dropped_keys > 0:
        log.warning(f"Dropped {dropped_keys:,} rows with missing critical identifiers (order_date/order_id/sales)")

    # 4. De-duplicate on row_id
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["row_id"])
    dropped_dupes = before_dedup - len(df)
    if dropped_dupes > 0:
        log.info(f"Dropped {dropped_dupes:,} duplicate row_ids")

    # 5. Numeric hygiene and data type casting
    numeric_cols = ["sales", "profit", "discount", "shipping_cost", "quantity"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 6. Filter to US retail operations scope (9,994 order-line transactions)
    df = df[df["country"] == "United States"].copy()
    log.info(f"Filtered to United States geographical operations: {len(df):,} rows")

    # 7. Data Quality & Integrity Validation
    assert (df["sales"] >= 0).all(), "Data Quality Error: Negative sales values found"
    assert (df["discount"] >= 0).all() and (df["discount"] <= 1.0).all(), "Data Quality Error: Invalid discount values"
    assert (df["quantity"] >= 1).all(), "Data Quality Error: Quantity must be >= 1"

    # 8. Deterministic Synthetic Return Simulation
    # Note: Public Superstore lacks a verified return column. In production, this table
    # is joined with an Orders-Returns feed. For portfolio demonstration, returns are
    # deterministically modeled (seed=42) weighted toward high discount and unprofitable orders.
    rng = np.random.default_rng(seed=42)
    return_prob = np.clip(0.03 + (df["discount"] * 0.25) + (df["profit"] < 0) * 0.12, 0, 0.6)
    df["is_returned"] = (rng.random(len(df)) < return_prob).astype(int)
    returned_lines = int(df["is_returned"].sum())
    log.info(f"Simulated return flag generated: {returned_lines:,} returned lines ({returned_lines / len(df) * 100:.1f}%)")

    # 9. Format string fields and retain canonical schema columns
    keep_cols = [
        "row_id", "order_id", "order_date", "ship_date", "ship_mode",
        "customer_id", "customer_name", "segment", "city", "state",
        "country", "region", "category", "sub_category", "product_name",
        "sales", "quantity", "discount", "profit", "shipping_cost",
        "order_priority", "is_returned",
    ]
    df = df[keep_cols]
    log.info(f"Transform complete -> {len(df):,} validated rows ready for database load")
    return df


def load(df: pd.DataFrame, db_path: str = DB_PATH) -> None:
    """Execute DDL schema and load clean fact table into SQLite."""
    log.info(f"Loading data into SQLite warehouse: {db_path}")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    schema_path = os.path.join(BASE_DIR, "sql", "schema.sql")
    with sqlite3.connect(db_path) as conn:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        df_load = df.copy()
        df_load["order_date"] = df_load["order_date"].dt.strftime("%Y-%m-%d")
        df_load["ship_date"] = df_load["ship_date"].dt.strftime("%Y-%m-%d")
        df_load.to_sql("fact_sales", conn, if_exists="append", index=False)
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    log.info(f"Load complete -> fact_sales table populated with {count:,} records")


def run_etl(csv_path: str = RAW_CSV_PATH, db_path: str = DB_PATH) -> pd.DataFrame:
    """Run full Extract, Transform, Load pipeline."""
    raw = extract(csv_path)
    clean = transform(raw)
    load(clean, db_path)
    return clean


if __name__ == "__main__":
    run_etl()
