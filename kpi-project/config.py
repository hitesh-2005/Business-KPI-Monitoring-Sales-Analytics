"""
Central config for the KPI Monitoring & Alerting Platform.
Keeping every threshold / path here means alert_engine.py, kpi_engine.py
and run_pipeline.py never hardcode a magic number.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RAW_CSV_PATH = os.path.join(BASE_DIR, "data", "superstore_raw.csv")
DB_PATH = os.path.join(BASE_DIR, "data", "warehouse.db")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# ---------------------------------------------------------------
# Alert thresholds (% change vs prior comparable period)
# ---------------------------------------------------------------
THRESHOLDS = {
    "revenue_drop_pct": 15,     # alert if daily revenue falls >15% vs 7-day rolling avg
    "profit_drop_pct": 10,      # alert if daily profit falls >10% vs 7-day rolling avg
    "orders_drop_pct": 20,      # alert if order count falls >20% vs 7-day rolling avg
    "return_rate_pct": 10,      # alert if return rate exceeds 10% of orders
    "region_drop_pct": 25,      # alert if any single region's revenue falls >25% WoW
    "anomaly_zscore": 2.5,      # |z-score| beyond this = statistical anomaly
}

# ---------------------------------------------------------------
# Notification channels — DRY_RUN=True by default so the project
# runs end-to-end without needing real SMTP/Slack credentials.
# Flip to False and fill in env vars to send real notifications.
# ---------------------------------------------------------------
DRY_RUN = True

SMTP_CONFIG = {
    "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
    "port": int(os.environ.get("SMTP_PORT", 587)),
    "user": os.environ.get("SMTP_USER", ""),
    "password": os.environ.get("SMTP_PASSWORD", ""),
    "recipients": os.environ.get("ALERT_EMAILS", "analytics-team@example.com").split(","),
}

SLACK_CONFIG = {
    "webhook_url": os.environ.get("SLACK_WEBHOOK_URL", ""),
    "channel": os.environ.get("SLACK_CHANNEL", "#sales-alerts"),
}
