"""
Unit Tests for Dedicated Analytical SQL Queries
=================================================
Validates:
- Category revenue shares and profit margins
- Top products ranking with DENSE_RANK()
- Segment performance and Average Order Value (AOV)
- Global macro summary metrics
"""

import pandas as pd
import pytest

from analytics.kpi_engine import load_sql_queries


def test_category_breakdown_sql(in_memory_db):
    """Test category performance query, margins, and revenue share window function."""
    queries = load_sql_queries()
    cat_query = queries["GET_CATEGORY_BREAKDOWN"]

    df = pd.read_sql_query(cat_query, in_memory_db)
    assert len(df) == 3
    # Categories: Technology, Furniture, Office Supplies
    # Total revenue = 550 (Tech) + 300 (Furn) + 100 (Office) = 950.00
    assert df["revenue"].sum() == 950.0
    # Revenue share percentages must sum to 100.0%
    assert round(df["revenue_share_pct"].sum(), 1) == 100.0

    tech_row = df[df["category"] == "Technology"].iloc[0]
    assert tech_row["revenue"] == 550.0
    assert tech_row["profit"] == 120.0
    # Margin = 120 / 550 * 100 = 21.82%
    assert tech_row["profit_margin_pct"] == 21.82


def test_top_products_dense_rank_sql(in_memory_db):
    """Test top products ranking via DENSE_RANK() window function."""
    queries = load_sql_queries()
    prod_query = queries["GET_TOP_PRODUCTS"]

    df = pd.read_sql_query(prod_query, in_memory_db, params={"top_n": 5})
    assert len(df) == 4  # 4 distinct products in fixture

    # Top product is Smartphone A ($500 sales)
    assert df.iloc[0]["product_name"] == "Smartphone A"
    assert df.iloc[0]["revenue_rank"] == 1
    assert df.iloc[0]["revenue"] == 500.0

    # Ranks must be strictly ascending
    assert list(df["revenue_rank"]) == [1, 2, 3, 4]


def test_global_summary_sql(in_memory_db):
    """Test global macro summary metrics against fixture expectations."""
    queries = load_sql_queries()
    sum_query = queries["GET_GLOBAL_SUMMARY"]

    cur = in_memory_db.cursor()
    row = cur.execute(sum_query).fetchone()
    cols = [c[0] for c in cur.description]
    res = dict(zip(cols, row))

    assert res["total_revenue"] == 950.0
    assert res["total_profit"] == 110.0
    assert res["total_orders"] == 3  # ORD-101, ORD-102, ORD-103
    assert res["total_returned_orders"] == 1  # ORD-101
    assert res["avg_return_rate"] == 33.33  # 1 / 3 * 100 = 33.33%
    assert res["min_date"] == "2014-01-01"
    assert res["max_date"] == "2014-01-03"
