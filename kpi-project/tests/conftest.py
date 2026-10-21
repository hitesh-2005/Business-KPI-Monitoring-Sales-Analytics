"""
Test Fixtures — Automated Business KPI Monitoring & Sales Analytics Platform
=============================================================================
Provides clean, isolated SQLite databases in memory for deterministic unit testing.
Does not mutate or overwrite the production warehouse.db.
"""

import os
import sqlite3
import pytest
import pandas as pd

from config import BASE_DIR


@pytest.fixture
def sample_orders_df():
    """Deterministic fixture with known edge cases:
    - Order 101 placed on 2014-01-01: 2 line items, both returned.
    - Order 102 placed on 2014-01-01: 1 line item, not returned.
    - Day 2014-01-02: No orders placed (calendar gap).
    - Order 103 placed on 2014-01-03: 1 line item, not returned.
    """
    rows = [
        {
            "row_id": 1,
            "order_id": "ORD-101",
            "order_date": "2014-01-01",
            "ship_date": "2014-01-03",
            "ship_mode": "Standard Class",
            "customer_id": "CUST-1",
            "customer_name": "Alice Smith",
            "segment": "Consumer",
            "city": "New York",
            "state": "New York",
            "country": "United States",
            "region": "East",
            "category": "Technology",
            "sub_category": "Phones",
            "product_name": "Smartphone A",
            "sales": 500.0,
            "quantity": 1,
            "discount": 0.1,
            "profit": 100.0,
            "shipping_cost": 20.0,
            "order_priority": "Medium",
            "is_returned": 1,
        },
        {
            "row_id": 2,
            "order_id": "ORD-101",
            "order_date": "2014-01-01",
            "ship_date": "2014-01-03",
            "ship_mode": "Standard Class",
            "customer_id": "CUST-1",
            "customer_name": "Alice Smith",
            "segment": "Consumer",
            "city": "New York",
            "state": "New York",
            "country": "United States",
            "region": "East",
            "category": "Technology",
            "sub_category": "Accessories",
            "product_name": "Phone Case",
            "sales": 50.0,
            "quantity": 2,
            "discount": 0.0,
            "profit": 20.0,
            "shipping_cost": 5.0,
            "order_priority": "Medium",
            "is_returned": 1,
        },
        {
            "row_id": 3,
            "order_id": "ORD-102",
            "order_date": "2014-01-01",
            "ship_date": "2014-01-04",
            "ship_mode": "Second Class",
            "customer_id": "CUST-2",
            "customer_name": "Bob Jones",
            "segment": "Corporate",
            "city": "Los Angeles",
            "state": "California",
            "country": "United States",
            "region": "West",
            "category": "Furniture",
            "sub_category": "Chairs",
            "product_name": "Ergonomic Chair",
            "sales": 300.0,
            "quantity": 1,
            "discount": 0.2,
            "profit": -50.0,
            "shipping_cost": 30.0,
            "order_priority": "High",
            "is_returned": 0,
        },
        {
            "row_id": 4,
            "order_id": "ORD-103",
            "order_date": "2014-01-03",
            "ship_date": "2014-01-06",
            "ship_mode": "Standard Class",
            "customer_id": "CUST-3",
            "customer_name": "Charlie Brown",
            "segment": "Home Office",
            "city": "Chicago",
            "state": "Illinois",
            "country": "United States",
            "region": "Central",
            "category": "Office Supplies",
            "sub_category": "Paper",
            "product_name": "Copy Paper",
            "sales": 100.0,
            "quantity": 5,
            "discount": 0.0,
            "profit": 40.0,
            "shipping_cost": 10.0,
            "order_priority": "Low",
            "is_returned": 0,
        },
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def in_memory_db(sample_orders_df):
    """Initializes in-memory SQLite database populated with schema and test fixture."""
    conn = sqlite3.connect(":memory:")
    schema_path = os.path.join(BASE_DIR, "sql", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    sample_orders_df.to_sql("fact_sales", conn, if_exists="append", index=False)
    conn.commit()
    yield conn
    conn.close()
