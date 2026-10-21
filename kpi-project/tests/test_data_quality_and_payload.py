"""
Data Quality & Serialization Integration Tests
================================================
Validates:
- Warehouse fact_sales table invariants
- Unified dashboard_data.json schema completeness
- Consistency between database aggregations and JSON outputs
"""

import json
import os
import sqlite3
import pytest

from config import DB_PATH, OUTPUTS_DIR


def test_warehouse_fact_sales_invariants():
    """Verify data quality constraints directly against production SQLite warehouse."""
    if not os.path.exists(DB_PATH):
        pytest.skip("warehouse.db not initialized yet")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        total_rows = cur.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
        assert total_rows == 9994, f"Expected 9,994 fact rows, found {total_rows}"

        # No null order dates, order IDs, or sales
        nulls = cur.execute(
            "SELECT COUNT(*) FROM fact_sales WHERE order_date IS NULL OR order_id IS NULL OR sales IS NULL"
        ).fetchone()[0]
        assert nulls == 0, "Found null values in critical key columns"

        # Non-negative sales
        neg_sales = cur.execute("SELECT COUNT(*) FROM fact_sales WHERE sales < 0").fetchone()[0]
        assert neg_sales == 0, "Found negative sales records"

        # Valid discounts (0.0 <= discount <= 1.0)
        invalid_disc = cur.execute(
            "SELECT COUNT(*) FROM fact_sales WHERE discount < 0.0 OR discount > 1.0"
        ).fetchone()[0]
        assert invalid_disc == 0, "Found discount outside [0, 1] range"

        # Valid quantities (quantity >= 1)
        invalid_qty = cur.execute("SELECT COUNT(*) FROM fact_sales WHERE quantity < 1").fetchone()[0]
        assert invalid_qty == 0, "Found quantity < 1"


def test_dashboard_json_schema():
    """Verify generated dashboard_data.json has all required keys and valid types."""
    json_path = os.path.join(OUTPUTS_DIR, "dashboard_data.json")
    if not os.path.exists(json_path):
        pytest.skip("dashboard_data.json not generated yet")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_keys = [
        "generated_at",
        "metadata",
        "summary",
        "kpi_daily",
        "region_weekly",
        "top_products",
        "category_breakdown",
        "segment_breakdown",
        "forecast",
        "alerts",
    ]
    for key in required_keys:
        assert key in data, f"Missing required top-level key: {key}"

    # Summary validations
    summary = data["summary"]
    assert summary["total_revenue"] > 2_000_000.0
    assert summary["total_orders"] == 5009
    assert 0.0 <= summary["avg_return_rate"] <= 100.0

    # Ensure kpi_daily is continuous list
    assert len(data["kpi_daily"]) == 1458
