"""
Unit Tests for Anomaly Detection & Alert Engine Integration
============================================================
Validates:
- Z-score and Isolation Forest anomaly flagging
- Alert engine consuming statistical anomaly outputs
- Partial-week alert suppression (preventing false alarms)
- Standard threshold breach logic
"""

import pandas as pd
import pytest

from alerts.alert_engine import evaluate_thresholds, evaluate_anomalies, evaluate_region_drops
from analytics.anomaly_detection import zscore_anomalies


def test_zscore_calculation_and_flagging():
    """Test rolling Z-score flagging on synthetic series."""
    dates = pd.date_range("2014-01-01", periods=15, freq="D")
    revenues = [1000.0] * 14 + [5000.0]  # Day 15 is a massive spike
    df = pd.DataFrame({"kpi_date": dates, "revenue": revenues, "is_active_day": 1})

    res = zscore_anomalies(df, column="revenue", window=14, threshold=2.5)

    assert "revenue_zscore" in res.columns
    assert "revenue_is_anomaly" in res.columns
    # Day 15 spike should be flagged as an anomaly
    assert bool(res.iloc[-1]["revenue_is_anomaly"]) is True
    # Initial stable days should not be flagged
    assert bool(res.iloc[5]["revenue_is_anomaly"]) is False


def test_alert_engine_consumes_anomaly_flags():
    """Verify that alert_engine generates alerts when anomaly flags are present."""
    anomalous_row = {
        "kpi_date": "2014-12-31",
        "revenue": 10000.0,
        "revenue_is_anomaly": True,
        "revenue_zscore": 3.45,
        "iso_forest_anomaly": True,
        "iso_forest_score": -0.15,
    }

    alerts = evaluate_anomalies(anomalous_row)
    assert len(alerts) == 2
    types = [a["alert_type"] for a in alerts]
    assert "STATISTICAL_ANOMALY" in types
    assert "MULTIVARIATE_ANOMALY" in types

    stat_alert = next(a for a in alerts if a["alert_type"] == "STATISTICAL_ANOMALY")
    assert stat_alert["severity"] == "CRITICAL"
    assert stat_alert["metric_value"] == 3.45


def test_partial_week_regional_alert_suppression():
    """Verify that truncated/partial weeks (< 5 active days) do NOT trigger false-positive alerts."""
    weekly_df = pd.DataFrame([
        {
            "region": "West",
            "week": pd.to_datetime("2014-12-29"),
            "revenue": 500.0,
            "active_days": 3,
            "is_partial_week": 1,
            "wow_pct": -75.0,  # 75% drop purely due to only 3 days of transactions
        }
    ])

    # With partial week protection, 0 alerts should be generated
    alerts = evaluate_region_drops(weekly_df)
    assert len(alerts) == 0

    # For a full week with same drop, an alert MUST be generated
    full_week_df = pd.DataFrame([
        {
            "region": "West",
            "week": pd.to_datetime("2014-12-22"),
            "revenue": 500.0,
            "active_days": 6,
            "is_partial_week": 0,
            "wow_pct": -45.0,
        }
    ])
    full_alerts = evaluate_region_drops(full_week_df)
    assert len(full_alerts) == 1
    assert full_alerts[0]["alert_type"] == "REGION_ANOMALY"
    assert full_alerts[0]["metric_value"] == -45.0


def test_standard_threshold_evaluation():
    """Verify threshold evaluation triggers for revenue and profit drops."""
    daily_row = {
        "kpi_date": "2014-12-31",
        "revenue": 500.0,
        "profit": -100.0,
        "orders": 5,
        "order_return_rate": 20.0,
    }
    baseline_7d = {
        "revenue": 1000.0,  # 50% drop
        "profit": 200.0,    # -150% drop
        "orders": 10,       # 50% drop
    }

    alerts = evaluate_thresholds(daily_row, baseline_7d)
    types = [a["alert_type"] for a in alerts]
    assert "REVENUE_DROP" in types
    assert "PROFIT_DROP" in types
    assert "ORDERS_DROP" in types
    assert "RETURN_SPIKE" in types
