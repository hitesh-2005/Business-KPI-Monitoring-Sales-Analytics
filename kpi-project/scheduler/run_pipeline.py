"""
run_pipeline.py — End-to-End Orchestrator for Daily KPI Monitoring & Sales Analytics
=====================================================================================
Executes the full automated workflow:
    1. ETL Pipeline          -> Extract raw sales, clean, validate, load SQLite fact_sales
    2. Analytical SQL Engine -> Compute continuous daily calendar, rolling windows, categories, products
    3. Anomaly Detection     -> Fit rolling Z-score & multivariate Isolation Forest
    4. Revenue Forecasting   -> Fit Holt-Winters Exponential Smoothing with non-negative bounds
    5. Alert Engine          -> Evaluate threshold drops & anomaly flags, dispatch notifications
    6. Dashboard Sync        -> Export payload to outputs/dashboard_data.json & kpi-frontend/public/

Execution:
    python scheduler/run_pipeline.py
"""

import json
import logging
import os
import shutil
import sys
import time

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OUTPUTS_DIR, LOGS_DIR, BASE_DIR
from etl.etl_pipeline import run_etl
from analytics.kpi_engine import run_kpi_engine
from analytics.anomaly_detection import detect_anomalies
from analytics.forecasting import forecast_revenue
from alerts.alert_engine import run_alert_engine

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | PIPELINE | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def export_dashboard_payload(daily, regions, products, categories, segments, summary, forecast, alerts) -> str:
    """Serialize and export analytical datasets to JSON for dashboard consumption."""
    frontend_public_dir = os.path.join(os.path.dirname(BASE_DIR), "kpi-frontend", "public")
    os.makedirs(frontend_public_dir, exist_ok=True)

    # Format dates as ISO strings
    daily_export = daily.copy()
    daily_export["kpi_date"] = daily_export["kpi_date"].astype(str)

    regions_export = regions.copy()
    regions_export["week"] = regions_export["week"].astype(str)
    if "week_end" in regions_export.columns:
        regions_export["week_end"] = regions_export["week_end"].astype(str)

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metadata": {
            "dataset_name": "Superstore US Commercial Sales",
            "scope": "United States Operations (2011–2014)",
            "fact_rows": 9994,
            "disclosures": {
                "returns": "Synthetic deterministic return flag (seed=42) modeled for portfolio demonstration.",
                "calendar": "Gapless continuous daily series zero-filled for non-trading weekend/holiday dates.",
            },
        },
        "summary": summary,
        "kpi_daily": json.loads(daily_export.to_json(orient="records")),
        "region_weekly": json.loads(regions_export.to_json(orient="records")),
        "top_products": json.loads(products.to_json(orient="records")),
        "category_breakdown": json.loads(categories.to_json(orient="records")),
        "segment_breakdown": json.loads(segments.to_json(orient="records")),
        "forecast": json.loads(forecast.to_json(orient="records")),
        "alerts": alerts,
    }

    out_file = os.path.join(OUTPUTS_DIR, "dashboard_data.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    log.info(f"Dashboard payload exported to pipeline outputs: {out_file}")

    # Sync directly with frontend public directory
    frontend_file = os.path.join(frontend_public_dir, "dashboard_data.json")
    try:
        shutil.copyfile(out_file, frontend_file)
        log.info(f"Synchronized payload with frontend public directory: {frontend_file}")
    except Exception as e:
        log.warning(f"Frontend public sync skipped: {e}")

    return out_file


def main():
    start_time = time.time()
    log.info("=" * 70)
    log.info("STARTING AUTOMATED BUSINESS KPI MONITORING PIPELINE")
    log.info("=" * 70)

    # 1. Ingestion & Transformation
    log.info("STAGE 1/6 — Extract, Transform, Load (ETL)")
    run_etl()

    # 2. Analytical SQL KPI Engine
    log.info("STAGE 2/6 — Analytical SQL Engine (Recursive CTEs & Window Functions)")
    kpi_results = run_kpi_engine()

    # 3. Statistical Anomaly Detection
    log.info("STAGE 3/6 — Statistical Anomaly Detection (Z-Score + Isolation Forest)")
    daily_enriched = detect_anomalies(kpi_results["daily"])

    # 4. Revenue Forecasting
    log.info("STAGE 4/6 — Revenue Forecasting (Holt-Winters with Additive Seasonality)")
    forecast = forecast_revenue(daily_enriched, periods=14)

    # 5. Alert Evaluation & Notification Dispatch
    log.info("STAGE 5/6 — Alert Evaluation & Notification Dispatch")
    alerts = run_alert_engine(daily_enriched, kpi_results["regions"])

    # 6. Export Dashboard Payloads
    log.info("STAGE 6/6 — Exporting Unified Dashboard Payload")
    export_dashboard_payload(
        daily=daily_enriched,
        regions=kpi_results["regions"],
        products=kpi_results["products"],
        categories=kpi_results["categories"],
        segments=kpi_results["segments"],
        summary=kpi_results["summary"],
        forecast=forecast,
        alerts=alerts,
    )

    elapsed = time.time() - start_time
    log.info("=" * 70)
    log.info(f"PIPELINE COMPLETED SUCCESSFULLY in {elapsed:.2f}s | {len(alerts)} alert(s) generated")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
