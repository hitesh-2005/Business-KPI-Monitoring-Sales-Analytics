# Scheduling the Pipeline

## Option A — Cron (simplest, good for a single server)

Run every day at 6:00 AM:

```bash
crontab -e
```

Add:

```
0 6 * * * cd /path/to/kpi-project && /usr/bin/python3 scheduler/run_pipeline.py >> logs/cron.log 2>&1
```

## Option B — Airflow DAG (production-style orchestration)

```python
# dags/kpi_monitoring_dag.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "analytics",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="daily_kpi_monitoring",
    default_args=default_args,
    schedule_interval="0 6 * * *",   # every day at 6 AM
    start_date=datetime(2026, 1, 1),
    catchup=False,
) as dag:

    run_pipeline = BashOperator(
        task_id="run_kpi_pipeline",
        bash_command="cd /path/to/kpi-project && python3 scheduler/run_pipeline.py",
    )
```

## Option C — Windows Task Scheduler

Program: `python.exe`
Arguments: `scheduler\run_pipeline.py`
Start in: `C:\path\to\kpi-project`
Trigger: Daily, 6:00 AM
