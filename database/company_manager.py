"""Company Manager — CRUD for company profiles with encrypted credentials.

Stores company data in data/companies.json (NOT in the demo PostgreSQL).
Each company has its own DB config, SMTP config, column mapping, and selected tables.
"""
import json
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Storage Path ──────────────────────────────────────────────────────────────
DATA_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "data"
COMPANIES_FILE = DATA_DIR / "companies.json"
SECRET_KEY_FILE = DATA_DIR / ".secret_key"


# ── Encryption ────────────────────────────────────────────────────────────────

def _get_fernet():
    """Get Fernet cipher for encrypting/decrypting SMTP passwords."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        logger.warning("cryptography not installed — passwords stored as base64 only")
        return None

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_KEY_FILE.exists():
        key = SECRET_KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        SECRET_KEY_FILE.write_bytes(key)
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """Encrypt a sensitive value."""
    f = _get_fernet()
    if f and value:
        return f.encrypt(value.encode()).decode()
    return value


def decrypt_value(value: str) -> str:
    """Decrypt a sensitive value."""
    f = _get_fernet()
    if f and value:
        try:
            return f.decrypt(value.encode()).decode()
        except Exception:
            return value
    return value


# ── Company CRUD ──────────────────────────────────────────────────────────────

def _load_all() -> dict:
    """Load all companies from JSON."""
    if not COMPANIES_FILE.exists():
        return {}
    try:
        with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading companies: {e}")
        return {}


def _save_all(data: dict):
    """Save all companies to JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(COMPANIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def create_company(name: str, email: str, recipients: list = None) -> dict:
    """Create a new company profile.

    Args:
        name: Company name
        email: Primary company email
        recipients: List of report recipient emails

    Returns:
        The created company dict
    """
    companies = _load_all()
    company_id = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"

    company = {
        "company_id": company_id,
        "name": name,
        "email": email,
        "recipients": recipients or [email],
        "db_config": {},
        "smtp_config": {},
        "column_mapping": {},
        "selected_tables": [],
        "created_at": datetime.now().isoformat(),
    }

    companies[company_id] = company
    _save_all(companies)
    logger.info(f"Company created: {name} ({company_id})")
    return company


def get_company(company_id: str) -> Optional[dict]:
    """Get a company by ID."""
    return _load_all().get(company_id)


def list_companies() -> list:
    """List all companies."""
    return list(_load_all().values())


def update_company(company_id: str, **kwargs) -> Optional[dict]:
    """Update company fields."""
    companies = _load_all()
    if company_id not in companies:
        return None
    companies[company_id].update(kwargs)
    _save_all(companies)
    return companies[company_id]


def delete_company(company_id: str) -> bool:
    """Delete a company."""
    companies = _load_all()
    if company_id in companies:
        del companies[company_id]
        _save_all(companies)
        return True
    return False


# ── Database Config ───────────────────────────────────────────────────────────

def save_db_config(company_id: str, db_config: dict) -> bool:
    """Save database connection config for a company.

    Args:
        company_id: Company ID
        db_config: {db_type, host, port, database, username, password, schema, ...}
    """
    companies = _load_all()
    if company_id not in companies:
        return False

    # Don't store raw password — encrypt it
    config = db_config.copy()
    if "password" in config and config["password"]:
        config["password_encrypted"] = encrypt_value(config.pop("password"))
    elif "password" in config:
        config.pop("password")

    companies[company_id]["db_config"] = config
    _save_all(companies)
    return True


def get_db_config(company_id: str) -> dict:
    """Get database config with decrypted password."""
    company = get_company(company_id)
    if not company:
        return {}

    config = company.get("db_config", {}).copy()
    if "password_encrypted" in config:
        config["password"] = decrypt_value(config.pop("password_encrypted"))
    return config


# ── SMTP / Email Config ──────────────────────────────────────────────────────

def save_smtp_config(company_id: str, smtp_config: dict) -> bool:
    """Save SMTP email config for a company.

    Args:
        company_id: Company ID
        smtp_config: {host, port, username, password, sender_email}
    """
    companies = _load_all()
    if company_id not in companies:
        return False

    config = smtp_config.copy()
    if "password" in config and config["password"]:
        config["password_encrypted"] = encrypt_value(config.pop("password"))
    elif "password" in config:
        config.pop("password")

    companies[company_id]["smtp_config"] = config
    _save_all(companies)
    return True


def get_smtp_config(company_id: str) -> dict:
    """Get SMTP config with decrypted password."""
    company = get_company(company_id)
    if not company:
        return {}

    config = company.get("smtp_config", {}).copy()
    if "password_encrypted" in config:
        config["password"] = decrypt_value(config.pop("password_encrypted"))
    return config


# ── Column Mapping ────────────────────────────────────────────────────────────

STANDARD_FIELDS = [
    "order_id", "order_date", "product_id", "product_name",
    "customer_id", "customer_name", "quantity", "sales_amount",
    "unit_price", "store_id", "store_name", "payment_method",
    "category", "region", "city", "state",
]


def save_column_mapping(company_id: str, mapping: dict) -> bool:
    """Save column mapping for a company.

    Args:
        mapping: {standard_field: company_column, ...}
    """
    companies = _load_all()
    if company_id not in companies:
        return False
    companies[company_id]["column_mapping"] = mapping
    _save_all(companies)
    return True


def get_column_mapping(company_id: str) -> dict:
    """Get column mapping for a company."""
    company = get_company(company_id)
    return company.get("column_mapping", {}) if company else {}


# ── Selected Tables ───────────────────────────────────────────────────────────

def save_selected_tables(company_id: str, tables: list) -> bool:
    """Save selected tables for a company."""
    companies = _load_all()
    if company_id not in companies:
        return False
    companies[company_id]["selected_tables"] = tables
    _save_all(companies)
    return True


def get_selected_tables(company_id: str) -> list:
    """Get selected tables for a company."""
    company = get_company(company_id)
    return company.get("selected_tables", []) if company else []
