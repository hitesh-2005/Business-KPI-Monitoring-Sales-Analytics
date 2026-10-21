"""
Alert Engine — Automated Business KPI Monitoring & Sales Analytics Platform
=============================================================================
Evaluates the latest business metrics against both operational business thresholds
and statistical anomaly models (Z-score + Isolation Forest).

Key Features & Reliability Guardrails:
1. Direct Anomaly Integration: Consumes Z-score and Isolation Forest flags.
2. Incomplete Week Protection: Detects partial week boundaries (e.g. final truncated week)
   and suppresses misleading false-positive regional drop alerts.
3. Mathematically Bounded Return Rate: Evaluates order-level return rate (0–100%).
4. Persistent SQLite Alert History: Logs all triggered breaches to alert_history.
5. Notification Channels: Supports Email (SMTP) and Slack webhook (DRY_RUN mode by default).

Execution:
    python alerts/alert_engine.py
"""

import logging
import os
import smtplib
import sqlite3
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText

import requests

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, THRESHOLDS, DRY_RUN, SMTP_CONFIG, SLACK_CONFIG, LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | ALERT | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "alerts.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def evaluate_thresholds(daily_row: dict, baseline_7d: dict) -> list[dict]:
    """Compare latest active trading day against trailing 7-day baseline."""
    alerts = []
    kpi_date = str(daily_row["kpi_date"])[:10]

    def safe_pct_change(current, base):
        if not base or base == 0:
            return 0.0
        return (current - base) / base * 100.0

    # 1. Revenue Drop Check
    rev_change = safe_pct_change(daily_row["revenue"], baseline_7d["revenue"])
    if rev_change <= -THRESHOLDS["revenue_drop_pct"]:
        alerts.append({
            "alert_type": "REVENUE_DROP",
            "severity": "CRITICAL" if rev_change <= -30.0 else "WARNING",
            "metric_value": round(rev_change, 1),
            "threshold_value": -THRESHOLDS["revenue_drop_pct"],
            "message": f"Revenue on {kpi_date} (${daily_row['revenue']:,.2f}) is {abs(rev_change):.1f}% below trailing 7-day average (${baseline_7d['revenue']:,.2f}).",
        })

    # 2. Profit Drop Check
    profit_change = safe_pct_change(daily_row["profit"], baseline_7d["profit"])
    if profit_change <= -THRESHOLDS["profit_drop_pct"]:
        alerts.append({
            "alert_type": "PROFIT_DROP",
            "severity": "CRITICAL" if profit_change <= -25.0 else "WARNING",
            "metric_value": round(profit_change, 1),
            "threshold_value": -THRESHOLDS["profit_drop_pct"],
            "message": f"Profit on {kpi_date} (${daily_row['profit']:,.2f}) is {abs(profit_change):.1f}% below trailing 7-day average (${baseline_7d['profit']:,.2f}).",
        })

    # 3. Order Count Drop Check
    orders_change = safe_pct_change(daily_row["orders"], baseline_7d["orders"])
    if orders_change <= -THRESHOLDS["orders_drop_pct"]:
        alerts.append({
            "alert_type": "ORDERS_DROP",
            "severity": "WARNING",
            "metric_value": round(orders_change, 1),
            "threshold_value": -THRESHOLDS["orders_drop_pct"],
            "message": f"Order count on {kpi_date} ({daily_row['orders']}) is {abs(orders_change):.1f}% below trailing 7-day average ({baseline_7d['orders']:.1f}).",
        })

    # 4. Return Rate Spike (Order Return Rate Bounded 0-100%)
    ret_rate = daily_row.get("order_return_rate", 0.0)
    if ret_rate is not None and ret_rate >= THRESHOLDS["return_rate_pct"]:
        alerts.append({
            "alert_type": "RETURN_SPIKE",
            "severity": "CRITICAL" if ret_rate >= 25.0 else "WARNING",
            "metric_value": round(ret_rate, 1),
            "threshold_value": THRESHOLDS["return_rate_pct"],
            "message": f"Order return rate on {kpi_date} reached {ret_rate:.1f}%, exceeding {THRESHOLDS['return_rate_pct']}% operational threshold.",
        })

    return alerts


def evaluate_anomalies(daily_row: dict) -> list[dict]:
    """Consume statistical anomaly flags from Z-score and Isolation Forest models."""
    alerts = []
    kpi_date = str(daily_row["kpi_date"])[:10]

    # Check Z-score statistical anomaly
    if daily_row.get("revenue_is_anomaly"):
        zscore = daily_row.get("revenue_zscore", 0.0)
        alerts.append({
            "alert_type": "STATISTICAL_ANOMALY",
            "severity": "CRITICAL" if abs(zscore) >= 3.0 else "WARNING",
            "metric_value": round(float(zscore), 2),
            "threshold_value": THRESHOLDS["anomaly_zscore"],
            "message": f"Statistical outlier on {kpi_date}: Daily revenue Z-score reached {zscore:.2f} (|z| > {THRESHOLDS['anomaly_zscore']}).",
        })

    # Check Multivariate Isolation Forest anomaly
    if daily_row.get("iso_forest_anomaly"):
        score = daily_row.get("iso_forest_score", 0.0)
        alerts.append({
            "alert_type": "MULTIVARIATE_ANOMALY",
            "severity": "WARNING",
            "metric_value": round(float(score), 3),
            "threshold_value": 0.0,
            "message": f"Multivariate anomaly on {kpi_date}: Isolation Forest flagged joint disruption across revenue, profit, orders, and discount (score: {score:.3f}).",
        })

    return alerts


def evaluate_region_drops(weekly_region_df) -> list[dict]:
    """Evaluate regional WoW drops, explicitly protecting against partial week boundary traps."""
    alerts = []
    if weekly_region_df.empty:
        return alerts

    latest_week = weekly_region_df["week"].max()
    latest_rows = weekly_region_df[weekly_region_df["week"] == latest_week]

    for _, row in latest_rows.iterrows():
        # Check if week is incomplete (< 5 active days)
        if row.get("is_partial_week", 0) == 1:
            log.info(f"Skipping WoW evaluation for {row['region']} (partial week of {str(row['week'])[:10]} with {row['active_days']} days)")
            continue

        wow_pct = row.get("wow_pct")
        if wow_pct is not None and wow_pct <= -THRESHOLDS["region_drop_pct"]:
            alerts.append({
                "alert_type": "REGION_ANOMALY",
                "severity": "WARNING",
                "metric_value": round(float(wow_pct), 1),
                "threshold_value": -THRESHOLDS["region_drop_pct"],
                "message": f"{row['region']} region revenue dropped {abs(wow_pct):.1f}% WoW in complete week of {str(row['week'])[:10]}.",
            })

    return alerts


def send_email(subject: str, body: str) -> str:
    """Send notification via SMTP (or mock in DRY_RUN mode)."""
    if DRY_RUN:
        log.info(f"[DRY RUN] EMAIL -> {SMTP_CONFIG['recipients']} | Subject: {subject}")
        return "DRY_RUN"
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_CONFIG["user"]
        msg["To"] = ", ".join(SMTP_CONFIG["recipients"])
        with smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"], timeout=10) as server:
            server.starttls()
            server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
            server.sendmail(SMTP_CONFIG["user"], SMTP_CONFIG["recipients"], msg.as_string())
        return "EMAIL_SENT"
    except Exception as e:
        log.error(f"Email dispatch failed: {e}")
        return "EMAIL_FAILED"


def send_slack(text: str) -> str:
    """Send notification via Slack Webhook (or mock in DRY_RUN mode)."""
    if DRY_RUN:
        log.info(f"[DRY RUN] SLACK {SLACK_CONFIG['channel']} -> {text}")
        return "DRY_RUN"
    try:
        resp = requests.post(SLACK_CONFIG["webhook_url"], json={"text": text}, timeout=5)
        resp.raise_for_status()
        return "SLACK_SENT"
    except Exception as e:
        log.error(f"Slack dispatch failed: {e}")
        return "SLACK_FAILED"


def log_alert_to_db(alert: dict, channel: str, db_path: str = DB_PATH) -> None:
    """Persist alert into SQLite alert_history table."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO alert_history
               (triggered_at, alert_type, severity, metric_value, threshold_value, message, channel_sent)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                alert["alert_type"],
                alert["severity"],
                alert["metric_value"],
                alert["threshold_value"],
                alert["message"],
                channel,
            ),
        )
        conn.commit()


def dispatch_alerts(alerts: list[dict], db_path: str = DB_PATH) -> None:
    """Dispatch alerts to notification channels and record in database."""
    if not alerts:
        log.info("All metrics within nominal operational thresholds — 0 alerts triggered.")
        return

    for alert in alerts:
        tag = f"[{alert['severity']}]"
        subject = f"{tag} {alert['alert_type'].replace('_', ' ').title()}"
        body = alert["message"]

        email_status = send_email(subject, body)
        slack_status = send_slack(f"*{alert['alert_type']}*: {body}")

        log_alert_to_db(alert, channel=f"{email_status}+{slack_status}", db_path=db_path)
        log.info(f"{subject} - {body}")


def run_alert_engine(daily_df, weekly_region_df, db_path: str = DB_PATH) -> list[dict]:
    """Run full alert evaluation pipeline."""
    # Isolate active trading days to find the latest valid operational day
    active_days = daily_df[daily_df["is_active_day"] == 1] if "is_active_day" in daily_df.columns else daily_df
    if active_days.empty:
        log.warning("No active sales days available to evaluate alerts.")
        return []

    latest_row = active_days.iloc[-1].to_dict()

    # Trailing 7 calendar-day baseline prior to the latest active day
    latest_idx = daily_df.index[daily_df["kpi_date"] == latest_row["kpi_date"]].tolist()
    if latest_idx:
        end_pos = latest_idx[0]
        start_pos = max(0, end_pos - 7)
        prior_window = daily_df.iloc[start_pos:end_pos]
    else:
        prior_window = daily_df.iloc[-8:-1]

    baseline_7d = {
        "revenue": prior_window["revenue"].mean() if not prior_window.empty else 1.0,
        "profit": prior_window["profit"].mean() if not prior_window.empty else 1.0,
        "orders": prior_window["orders"].mean() if not prior_window.empty else 1.0,
    }

    # Evaluate all alert rules
    alerts = evaluate_thresholds(latest_row, baseline_7d)
    alerts += evaluate_anomalies(latest_row)
    alerts += evaluate_region_drops(weekly_region_df)

    dispatch_alerts(alerts, db_path=db_path)
    return alerts


if __name__ == "__main__":
    from analytics.kpi_engine import run_kpi_engine
    from analytics.anomaly_detection import detect_anomalies

    res = run_kpi_engine()
    daily_enriched = detect_anomalies(res["daily"])
    fired_alerts = run_alert_engine(daily_enriched, res["regions"])
    print(f"\nAlert Engine Complete. {len(fired_alerts)} alerts fired.")
