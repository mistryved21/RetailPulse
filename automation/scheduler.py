"""Automated Report Scheduler for RetailPulse.

Manages recurring daily, weekly, and monthly automated executive reports
and email dispatch per company using APScheduler.
"""
import datetime
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

SCHEDULES_FILE = os.path.join(os.getcwd(), "data", "schedules.json")


def _ensure_data_dir():
    os.makedirs(os.path.join(os.getcwd(), "data"), exist_ok=True)
    if not os.path.exists(SCHEDULES_FILE):
        with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def list_schedules(company_id: str = None) -> list[dict]:
    """List scheduled reports, optionally filtered by company."""
    _ensure_data_dir()
    try:
        with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
            schedules = json.load(f)
        if company_id:
            return [s for s in schedules if s.get("company_id") == company_id]
        return schedules
    except Exception as e:
        logger.error(f"Error reading schedules: {e}")
        return []


def create_schedule(
    company_id: str,
    company_name: str,
    report_title: str,
    frequency: str = "weekly",
    time_of_day: str = "09:00",
    recipients: list = None
) -> dict:
    """Register a new recurring executive report schedule."""
    _ensure_data_dir()
    schedules = list_schedules()
    import uuid
    new_sched = {
        "id": f"sched_{uuid.uuid4().hex[:8]}",
        "company_id": company_id,
        "company_name": company_name,
        "report_title": report_title,
        "frequency": frequency.lower(),
        "time_of_day": time_of_day,
        "recipients": recipients or [],
        "enabled": True,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_run": None,
        "status": "Active"
    }
    schedules.append(new_sched)
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2)
        
    logger.info(f"Created schedule {new_sched['id']} for {company_name}")
    return new_sched


def delete_schedule(schedule_id: str) -> bool:
    """Delete a scheduled report."""
    _ensure_data_dir()
    schedules = list_schedules()
    filtered = [s for s in schedules if s.get("id") != schedule_id]
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2)
    return len(filtered) < len(schedules)


def toggle_schedule(schedule_id: str, enabled: bool) -> bool:
    """Enable or disable a scheduled report."""
    _ensure_data_dir()
    schedules = list_schedules()
    for s in schedules:
        if s.get("id") == schedule_id:
            s["enabled"] = enabled
            s["status"] = "Active" if enabled else "Paused"
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2)
    return True
