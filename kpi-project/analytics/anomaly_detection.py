"""
Anomaly Detection — Automated Business KPI Monitoring & Sales Analytics Platform
==================================================================================
Identifies statistically unusual sales and margin patterns using two complementary
analytical methods:

1. Rolling Z-Score:
   Tracks standard deviations of daily revenue and profit from a trailing baseline.
   Transparent, fast, and easily explained to business stakeholders.

2. Multivariate Isolation Forest:
   Unsupervised tree ensemble evaluating joint feature interactions
   (revenue, profit, order volume, weighted discount) to detect multidimensional
   disruptions that univariate tests overlook.

Note on Methodology:
   Anomaly detection flags statistical divergence from historical distributions.
   It does not determine root-cause business causation. The contamination parameter
   represents the expected fraction of outliers in the training distribution.

Execution:
    python analytics/anomaly_detection.py
"""

import logging
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import THRESHOLDS, LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | ANOMALY | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "anomaly.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def zscore_anomalies(
    daily: pd.DataFrame, column: str = "revenue", window: int = 14, threshold: float = None
) -> pd.DataFrame:
    """Calculate rolling Z-scores for active trading days against a trailing baseline window."""
    if threshold is None:
        threshold = THRESHOLDS.get("anomaly_zscore", 2.5)

    daily = daily.copy()
    # Compute rolling mean and std on active trading days to prevent synthetic zero-fill days from skewing variance
    active_mask = daily["is_active_day"] == 1 if "is_active_day" in daily.columns else pd.Series(True, index=daily.index)

    roll_mean = daily.loc[active_mask, column].rolling(window, min_periods=5).mean()
    roll_std = daily.loc[active_mask, column].rolling(window, min_periods=5).std().replace(0, np.nan)

    daily[f"{column}_zscore"] = np.nan
    daily.loc[active_mask, f"{column}_zscore"] = (daily.loc[active_mask, column] - roll_mean) / roll_std
    daily[f"{column}_is_anomaly"] = daily[f"{column}_zscore"].abs() > threshold
    daily[f"{column}_is_anomaly"] = daily[f"{column}_is_anomaly"].fillna(False)

    flagged_count = int(daily[f"{column}_is_anomaly"].sum())
    log.info(f"Z-Score ({column}): {flagged_count} anomalies flagged (|z| > {threshold})")
    return daily


def isolation_forest_anomalies(
    daily: pd.DataFrame, contamination: float = 0.03, random_state: int = 42
) -> pd.DataFrame:
    """Multivariate anomaly detection across revenue, profit, orders, and discount distributions."""
    daily = daily.copy()
    feature_cols = ["revenue", "profit", "orders", "weighted_discount"]
    for col in feature_cols:
        if col not in daily.columns:
            daily[col] = 0.0

    active_mask = daily["is_active_day"] == 1 if "is_active_day" in daily.columns else pd.Series(True, index=daily.index)
    active_df = daily[active_mask]

    daily["iso_forest_anomaly"] = False
    daily["iso_forest_score"] = 0.0

    if len(active_df) >= 30:
        features = active_df[feature_cols].fillna(0)
        model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=150,
            n_jobs=-1,
        )
        preds = model.fit_predict(features)  # -1 = anomaly, 1 = normal
        scores = model.decision_function(features)  # Lower score = higher anomaly likelihood

        daily.loc[active_mask, "iso_forest_anomaly"] = preds == -1
        daily.loc[active_mask, "iso_forest_score"] = scores.round(4)

        flagged_count = int(daily["iso_forest_anomaly"].sum())
        log.info(f"Isolation Forest: {flagged_count} multivariate anomalies flagged (contamination={contamination})")
    else:
        log.warning("Insufficient active trading days to fit Isolation Forest (< 30 days). Skipping.")

    return daily


def detect_anomalies(daily: pd.DataFrame) -> pd.DataFrame:
    """Run full anomaly detection suite and synthesize composite anomaly flags."""
    daily = zscore_anomalies(daily, column="revenue")
    daily = zscore_anomalies(daily, column="profit")
    daily = isolation_forest_anomalies(daily)

    active_mask = daily["is_active_day"] == 1 if "is_active_day" in daily.columns else pd.Series(True, index=daily.index)
    daily["is_anomaly"] = (
        daily["revenue_is_anomaly"] | daily["profit_is_anomaly"] | daily["iso_forest_anomaly"]
    ) & active_mask

    total_anomalies = int(daily["is_anomaly"].sum())
    log.info(f"Total Anomalous Days Flagged: {total_anomalies} out of {int(active_mask.sum())} active days")
    return daily


if __name__ == "__main__":
    from analytics.kpi_engine import run_kpi_engine
    results = run_kpi_engine()
    daily_anomalies = detect_anomalies(results["daily"])
    flagged = daily_anomalies[daily_anomalies["is_anomaly"]]
    print("\nSample Detected Anomalies (Latest 5):")
    print(flagged[["kpi_date", "revenue", "profit", "revenue_zscore", "profit_zscore", "iso_forest_score"]].tail(5).to_string(index=False))
