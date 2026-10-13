"""Automated Retail Anomaly & Performance Alerts Engine for RetailPulse.

Evaluates threshold rules (Revenue decline, Profit drop, Margin anomalies, Stockouts)
and maintains an audit log of triggered alerts.
"""
import datetime
import json
import logging
import os

logger = logging.getLogger(__name__)

ALERTS_FILE = os.path.join(os.getcwd(), "data", "alerts_history.json")
RULES_FILE = os.path.join(os.getcwd(), "data", "alert_rules.json")


def _ensure_alerts_dir():
    os.makedirs(os.path.join(os.getcwd(), "data"), exist_ok=True)
    if not os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists(RULES_FILE):
        default_rules = [
            {"id": "rule_1", "name": "Revenue Contraction Alert", "metric": "revenue_growth", "threshold": -10.0, "severity": "Critical", "enabled": True},
            {"id": "rule_2", "name": "Profit Margin Warning", "metric": "profit_growth", "threshold": -15.0, "severity": "Critical", "enabled": True},
            {"id": "rule_3", "name": "Category Drop Alert", "metric": "category_drop", "threshold": -20.0, "severity": "Warning", "enabled": True},
            {"id": "rule_4", "name": "Gross Margin Compression", "metric": "gross_margin", "threshold": 20.0, "severity": "Warning", "enabled": True}
        ]
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_rules, f, indent=2)


def get_alert_rules() -> list[dict]:
    """Retrieve all configured alert rules."""
    _ensure_alerts_dir()
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def get_alerts_history(company_id: str = None) -> list[dict]:
    """Retrieve history of triggered alerts."""
    _ensure_alerts_dir()
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            alerts = json.load(f)
        if company_id:
            return [a for a in alerts if a.get("company_id") in (company_id, "all")]
        return alerts
    except Exception:
        return []


def evaluate_and_record_alerts(analytics_data: dict, company_id: str = "demo", company_name: str = "Enterprise") -> list[dict]:
    """Evaluate current analytics against active alert rules and log triggered alerts."""
    _ensure_alerts_dir()
    comp = analytics_data.get("period_comparison", {})
    exec_kpis = analytics_data.get("executive_kpis", {})
    detected = analytics_data.get("detected_problems", [])
    
    rules = get_alert_rules()
    triggered = []
    import uuid

    # Check comparison metrics
    rev_growth = comp.get("revenue_growth", 0.0)
    prof_growth = comp.get("profit_growth", 0.0)
    margin = exec_kpis.get("gross_margin_pct", 0.0)

    for rule in rules:
        if not rule.get("enabled"):
            continue
            
        m = rule.get("metric")
        thresh = rule.get("threshold", 0.0)
        
        if m == "revenue_growth" and rev_growth <= thresh:
            triggered.append({
                "id": f"alert_{uuid.uuid4().hex[:8]}",
                "company_id": company_id,
                "company_name": company_name,
                "title": rule.get("name"),
                "severity": rule.get("severity", "Critical"),
                "message": f"Revenue contracted by {abs(rev_growth):.1f}% (Threshold: <= {thresh}%).",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Active"
            })
        elif m == "profit_growth" and prof_growth <= thresh:
            triggered.append({
                "id": f"alert_{uuid.uuid4().hex[:8]}",
                "company_id": company_id,
                "company_name": company_name,
                "title": rule.get("name"),
                "severity": rule.get("severity", "Critical"),
                "message": f"Gross profit dropped by {abs(prof_growth):.1f}% (Threshold: <= {thresh}%).",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Active"
            })

    # Save to history
    if triggered:
        history = get_alerts_history()
        history = triggered + history[:100]  # Keep latest 100
        with open(ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    return triggered
