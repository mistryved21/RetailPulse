"""Automation and scheduling package for RetailPulse."""
from automation.scheduler import list_schedules, create_schedule, delete_schedule, toggle_schedule
from automation.alerts import get_alert_rules, get_alerts_history, evaluate_and_record_alerts
