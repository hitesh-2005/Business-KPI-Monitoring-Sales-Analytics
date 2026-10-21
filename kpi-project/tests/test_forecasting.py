"""
Unit Tests for Revenue Forecasting Module
===========================================
Validates:
- 14-day projection generation
- Non-negative revenue lower bounds (clipped at 0.0)
- Graceful handling of insufficient history
- Seasonal naive fallback mechanism
"""

import pandas as pd
import pytest

from analytics.forecasting import forecast_revenue, seasonal_naive_fallback


def test_forecast_horizon_and_non_negative_bounds():
    """Verify that Holt-Winters returns 14 daily rows with guaranteed non-negative bounds."""
    # Create 60 days of synthetic daily sales with clear weekly pattern
    dates = pd.date_range("2014-01-01", periods=60, freq="D")
    base_sales = [1000, 1200, 1100, 1300, 1500, 800, 600] * 8 + [1000, 1200, 1100, 1300]
    df = pd.DataFrame({"kpi_date": dates, "revenue": base_sales})

    fc = forecast_revenue(df, periods=14)

    assert len(fc) == 14
    assert list(fc.columns) == ["date", "forecast_revenue", "lower_bound", "upper_bound"]

    # Invariants: Forecast and lower bounds must NEVER be negative
    assert (fc["forecast_revenue"] >= 0.0).all()
    assert (fc["lower_bound"] >= 0.0).all()
    assert (fc["upper_bound"] >= fc["forecast_revenue"]).all()
    assert (fc["forecast_revenue"] >= fc["lower_bound"]).all()


def test_forecast_insufficient_history():
    """Verify that fewer than 28 historical days returns empty DataFrame rather than crashing."""
    dates = pd.date_range("2014-01-01", periods=10, freq="D")
    df = pd.DataFrame({"kpi_date": dates, "revenue": [500] * 10})

    fc = forecast_revenue(df, periods=14)
    assert fc.empty


def test_seasonal_naive_fallback():
    """Verify seasonal naive fallback produces non-negative 14-day cycle."""
    dates = pd.date_range("2014-01-01", periods=14, freq="D")
    series = pd.Series([200, 300, 400, 500, 600, 100, 50] * 2, index=dates)

    fb = seasonal_naive_fallback(series, periods=14)
    assert len(fb) == 14
    assert (fb["forecast_revenue"] >= 0.0).all()
    assert (fb["lower_bound"] >= 0.0).all()
