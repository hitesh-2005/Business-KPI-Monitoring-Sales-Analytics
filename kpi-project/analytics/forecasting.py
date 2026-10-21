"""
Forecasting — Automated Business KPI Monitoring & Sales Analytics Platform
=============================================================================
Projects daily revenue for a 14-day horizon using Holt-Winters Exponential Smoothing
(additive trend + 7-day weekly seasonality, damped trend).

Key Enhancements & Reliability Guardrails:
1. Continuous daily calendar frequency (zero-filled for non-trading days).
2. Guaranteed non-negative bounds: Revenue and lower bounds are clipped at 0.00.
3. Transparent uncertainty labeling: Labeled as 'Uncertainty Interval (+/- 1.96 in-sample residual std)'
   rather than formal Bayesian or parametric confidence intervals.
4. Robust Seasonal Naive Fallback: If numerical convergence or matrix singularity occurs,
   falls back to repeating the trailing 7-day seasonal cycle safely.

Execution:
    python analytics/forecasting.py
"""

import logging
import os
import sys
import warnings

import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOGS_DIR

warnings.filterwarnings("ignore")
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | FORECAST | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "forecast.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def seasonal_naive_fallback(series: pd.Series, periods: int = 14) -> pd.DataFrame:
    """Fallback generator repeating the trailing 7-day seasonal cycle if model fitting fails."""
    log.warning("Utilizing 7-day Seasonal Naive fallback projection")
    last_7 = series.iloc[-7:].values
    repeats = (periods // 7) + 1
    fallback_values = (list(last_7) * repeats)[:periods]

    last_date = series.index[-1]
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=periods, freq="D")
    in_sample_std = series.diff(7).dropna().std() if len(series) >= 14 else 100.0

    df_out = pd.DataFrame({
        "date": future_dates.strftime("%Y-%m-%d"),
        "forecast_revenue": [round(max(0.0, float(v)), 2) for v in fallback_values],
        "lower_bound": [round(max(0.0, float(v) - 1.96 * in_sample_std), 2) for v in fallback_values],
        "upper_bound": [round(max(0.0, float(v) + 1.96 * in_sample_std), 2) for v in fallback_values],
    })
    return df_out


def forecast_revenue(daily: pd.DataFrame, periods: int = 14) -> pd.DataFrame:
    """Generate 14-day revenue forecast with additive weekly seasonality and non-negative bounds."""
    if len(daily) < 28:
        log.warning(f"Insufficient history ({len(daily)} days). Minimum 28 days required.")
        return pd.DataFrame(columns=["date", "forecast_revenue", "lower_bound", "upper_bound"])

    # Prepare strictly regular daily time series
    daily_indexed = daily.copy()
    daily_indexed["kpi_date"] = pd.to_datetime(daily_indexed["kpi_date"])
    series = daily_indexed.set_index("kpi_date")["revenue"].asfreq("D").fillna(0.0)

    try:
        model = ExponentialSmoothing(
            series,
            trend="add",
            seasonal="add",
            seasonal_periods=7,
            damped_trend=True,
            initialization_method="estimated",
        ).fit(optimized=True)

        forecast = model.forecast(periods)
        resid_std = float(model.resid.std())

        last_date = series.index[-1]
        future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=periods, freq="D")

        # Clip values to ensure realistic non-negative retail revenue bounds
        pred_rev = [round(max(0.0, float(v)), 2) for v in forecast.values]
        lower_b = [round(max(0.0, float(v) - 1.96 * resid_std), 2) for v in forecast.values]
        upper_b = [round(max(0.0, float(v) + 1.96 * resid_std), 2) for v in forecast.values]

        forecast_df = pd.DataFrame({
            "date": future_dates.strftime("%Y-%m-%d"),
            "forecast_revenue": pred_rev,
            "lower_bound": lower_b,
            "upper_bound": upper_b,
        })

        avg_pred = forecast_df["forecast_revenue"].mean()
        log.info(f"Forecasted {periods} days forward. Mean predicted daily revenue: ${avg_pred:,.2f}")
        return forecast_df

    except Exception as e:
        log.error(f"Holt-Winters fitting encountered numerical error: {e}. Switching to fallback.")
        return seasonal_naive_fallback(series, periods)


if __name__ == "__main__":
    from analytics.kpi_engine import run_kpi_engine
    res = run_kpi_engine()
    fc = forecast_revenue(res["daily"], periods=14)
    print("\n14-Day Revenue Forecast with Non-Negative Bounds:")
    print(fc.to_string(index=False))
