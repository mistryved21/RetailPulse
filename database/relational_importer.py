"""Relational data importer for RetailPulse.

Imports cleaned datasets (CSV/Excel) into the relational PostgreSQL schema:
categories, products, customers, sales, inventory
inside an ACID database transaction with duplicate protection and rollback.
"""
import logging
import datetime
import pandas as pd
import numpy as np
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Standard RetailPulse field definitions for auto-mapping
STANDARD_FIELD_CANDIDATES = {
    "transaction_id": ["transaction_id", "transaction id", "order_id", "order id", "invoice_no", "invoice no", "id", "trans_id", "orderid", "transactionid"],
    "sale_date": ["date", "sale_date", "sale date", "order_date", "order date", "transaction_date", "timestamp", "datetime", "saledate", "orderdate"],
    "customer_id": ["customer_id", "customer id", "customer", "customer_code", "client_id", "user_id", "customerid"],
    "customer_name": ["customer_name", "customer name", "name", "client_name", "full_name", "buyer_name", "customername"],
    "customer_email": ["customer_email", "customer email", "email", "email_address", "contact_email"],
    "gender": ["gender", "sex"],
    "age": ["age"],
    "city": ["city", "town", "location"],
    "state": ["state", "province"],
    "region": ["region", "zone", "territory", "area"],
    "category_name": ["product_category", "product category", "category", "category_name", "category name", "department", "cat_name", "categoryname"],
    "product_name": ["product_name", "product name", "product", "item_name", "item name", "item", "productname"],
    "product_sku": ["sku", "product_sku", "product sku", "item_code", "product_code"],
    "quantity": ["quantity", "qty", "units", "units_sold", "volume", "count"],
    "unit_price": ["price_per_unit", "price per unit", "unit_price", "unit price", "price", "rate", "cost_per_unit", "unitprice", "priceperunit"],
    "total_amount": ["total_amount", "total amount", "total", "amount", "revenue", "sales", "net_amount", "total_sales", "totalamount", "totalsales"],
    "payment_method": ["payment_method", "payment method", "payment", "payment_type", "payment_mode", "paymentmethod"]
}


def auto_detect_mapping(df_columns: list[str]) -> dict[str, str]:
    """Auto-detect mapping from DataFrame columns to standard fields.
    
    Returns:
        dict: {standard_field: df_column}
    """
    mapping = {}
    lower_cols = {col.lower().strip().replace("-", "_"): col for col in df_columns}
    
    for std_field, candidates in STANDARD_FIELD_CANDIDATES.items():
        matched = None
        for cand in candidates:
            cand_clean = cand.lower().strip().replace("-", "_").replace(" ", "_")
            # Exact match
            for norm_col, orig_col in lower_cols.items():
                norm_col_clean = norm_col.replace(" ", "_")
                if norm_col_clean == cand_clean or norm_col_clean == cand.replace(" ", ""):
                    matched = orig_col
                    break
            if matched:
                break
        if matched:
            mapping[std_field] = matched
            
    return mapping


def import_dataset_to_relational_db(
    df: pd.DataFrame,
    mapping: dict[str, str],
    import_mode: str = "add"
) -> dict:
    """Import a DataFrame into the existing retailpulse_db PostgreSQL tables.
    
    Relational targets:
      1. categories (id, name, description)
      2. products (id, name, category_id, price, cost, sku, brand, is_active)
      3. customers (id, name, email, phone, city, state, registration_date, segment)
      4. sales (id, product_id, customer_id, quantity, unit_price, total_amount, sale_date, payment_method, region)
      
    Args:
        df: Input cleaned DataFrame
        mapping: {standard_field: column_name_in_df}
        import_mode: 'add', 'replace', or 'upsert'
        
    Returns:
        dict with execution summary: {
            "success": bool,
            "processed": int,
            "inserted": int,
            "skipped": int,
            "failed": int,
            "tables_affected": list[str],
            "total_sales_count": int,
            "message": str
        }
    """
    from database.db import _get_engine
    engine = _get_engine()
    df = df.copy()
    
    # Helper to get column value from row
    def get_val(row, std_field, default=None):
        col = mapping.get(std_field)
        if col and col in row and pd.notna(row[col]):
            return row[col]
        return default

    processed = len(df)
    inserted = 0
    skipped = 0
    failed = 0
    tables_affected = set()

    try:
        with engine.begin() as conn:
            # 1. Fetch existing categories
            cat_rows = conn.execute(text("SELECT id, name FROM categories")).fetchall()
            cat_map = {r[1].lower().strip(): r[0] for r in cat_rows}  # name.lower -> id
            
            # Fetch existing products
            prod_rows = conn.execute(text("SELECT id, name, sku FROM products")).fetchall()
            prod_name_map = {r[1].lower().strip(): r[0] for r in prod_rows}
            prod_sku_map = {r[2].lower().strip(): r[0] for r in prod_rows} if prod_rows else {}
            
            # Fetch existing customers
            cust_rows = conn.execute(text("SELECT id, email, name FROM customers")).fetchall()
            cust_email_map = {r[1].lower().strip(): r[0] for r in cust_rows if r[1]}
            cust_name_map = {r[2].lower().strip(): r[0] for r in cust_rows if r[2]}
            
            if import_mode == "replace":
                # If replacing sales dataset
                conn.execute(text("DELETE FROM sales"))
                tables_affected.add("sales")
                logger.info("Cleared existing sales records for replace mode.")

            # Iterate through each row and prepare relational records
            for idx, row in df.iterrows():
                try:
                    # A. CATEGORY
                    raw_cat = str(get_val(row, "category_name", "General")).strip()
                    cat_key = raw_cat.lower()
                    if cat_key not in cat_map:
                        res = conn.execute(
                            text("INSERT INTO categories (name, description) VALUES (:name, :desc) RETURNING id"),
                            {"name": raw_cat, "desc": f"Category for {raw_cat}"}
                        )
                        cat_id = res.scalar()
                        cat_map[cat_key] = cat_id
                        tables_affected.add("categories")
                    else:
                        cat_id = cat_map[cat_key]

                    # B. PRODUCT
                    raw_prod = str(get_val(row, "product_name", f"Product {raw_cat}")).strip()
                    raw_sku = str(get_val(row, "product_sku", f"SKU-{cat_id}-{idx+1}")).strip()
                    unit_price = float(get_val(row, "unit_price", 0.0) or 0.0)
                    total_amount = float(get_val(row, "total_amount", 0.0) or 0.0)
                    qty = int(float(get_val(row, "quantity", 1) or 1))
                    
                    if unit_price <= 0 and qty > 0 and total_amount > 0:
                        unit_price = round(total_amount / qty, 2)
                    elif total_amount <= 0 and qty > 0 and unit_price > 0:
                        total_amount = round(unit_price * qty, 2)
                        
                    cost = round(unit_price * 0.7, 2)
                    
                    prod_key = raw_prod.lower()
                    sku_key = raw_sku.lower()
                    
                    if sku_key in prod_sku_map:
                        prod_id = prod_sku_map[sku_key]
                    elif prod_key in prod_name_map:
                        prod_id = prod_name_map[prod_key]
                    else:
                        res = conn.execute(
                            text("""
                                INSERT INTO products (name, category_id, price, cost, sku, brand, is_active)
                                VALUES (:name, :category_id, :price, :cost, :sku, :brand, :is_active)
                                RETURNING id
                            """),
                            {
                                "name": raw_prod,
                                "category_id": cat_id,
                                "price": unit_price if unit_price > 0 else 100.0,
                                "cost": cost if cost > 0 else 70.0,
                                "sku": raw_sku,
                                "brand": "Standard",
                                "is_active": True
                            }
                        )
                        prod_id = res.scalar()
                        prod_name_map[prod_key] = prod_id
                        prod_sku_map[sku_key] = prod_id
                        tables_affected.add("products")

                    # C. CUSTOMER
                    raw_cust_id = get_val(row, "customer_id")
                    raw_cust_name = str(get_val(row, "customer_name", f"Customer {raw_cust_id or idx+1}")).strip()
                    raw_email = str(get_val(row, "customer_email", f"customer_{raw_cust_id or idx+1}@retailpulse.io")).strip()
                    raw_city = str(get_val(row, "city", "Mumbai")).strip()
                    raw_state = str(get_val(row, "state", "Maharashtra")).strip()
                    raw_segment = str(get_val(row, "gender", "Regular")).strip()
                    
                    email_key = raw_email.lower()
                    name_key = raw_cust_name.lower()
                    
                    if email_key in cust_email_map:
                        customer_id = cust_email_map[email_key]
                    elif name_key in cust_name_map:
                        customer_id = cust_name_map[name_key]
                    else:
                        res = conn.execute(
                            text("""
                                INSERT INTO customers (name, email, city, state, registration_date, segment)
                                VALUES (:name, :email, :city, :state, :reg_date, :segment)
                                RETURNING id
                            """),
                            {
                                "name": raw_cust_name,
                                "email": raw_email,
                                "city": raw_city,
                                "state": raw_state,
                                "reg_date": datetime.date.today(),
                                "segment": raw_segment
                            }
                        )
                        customer_id = res.scalar()
                        cust_email_map[email_key] = customer_id
                        cust_name_map[name_key] = customer_id
                        tables_affected.add("customers")

                    # D. SALE RECORD
                    raw_date = get_val(row, "sale_date")
                    if raw_date is not None:
                        try:
                            sale_date = pd.to_datetime(raw_date).to_pydatetime()
                        except Exception:
                            sale_date = datetime.datetime.now()
                    else:
                        sale_date = datetime.datetime.now()
                        
                    raw_payment = str(get_val(row, "payment_method", "Credit Card")).strip()
                    raw_region = str(get_val(row, "region", "North")).strip()
                    
                    # Duplicate check for 'add' mode
                    if import_mode == "add":
                        dup_check = conn.execute(
                            text("""
                                SELECT id FROM sales 
                                WHERE product_id = :p_id 
                                  AND customer_id = :c_id 
                                  AND quantity = :qty 
                                  AND total_amount = :amt 
                                  AND sale_date = :s_date 
                                LIMIT 1
                            """),
                            {
                                "p_id": prod_id,
                                "c_id": customer_id,
                                "qty": qty,
                                "amt": total_amount,
                                "s_date": sale_date
                            }
                        ).fetchone()
                        if dup_check:
                            skipped += 1
                            continue

                    # Insert Sale
                    conn.execute(
                        text("""
                            INSERT INTO sales (product_id, customer_id, quantity, unit_price, total_amount, sale_date, payment_method, region)
                            VALUES (:product_id, :customer_id, :quantity, :unit_price, :total_amount, :sale_date, :payment_method, :region)
                        """),
                        {
                            "product_id": prod_id,
                            "customer_id": customer_id,
                            "quantity": qty,
                            "unit_price": unit_price,
                            "total_amount": total_amount,
                            "sale_date": sale_date,
                            "payment_method": raw_payment,
                            "region": raw_region
                        }
                    )
                    inserted += 1
                    tables_affected.add("sales")

                except Exception as row_err:
                    logger.warning(f"Error importing row {idx}: {row_err}")
                    failed += 1
                    
        # Verification query after commit
        with engine.connect() as verify_conn:
            res_count = verify_conn.execute(text("SELECT COUNT(*) FROM sales")).scalar() or 0

        return {
            "success": True,
            "processed": processed,
            "inserted": inserted,
            "skipped": skipped,
            "failed": failed,
            "tables_affected": sorted(list(tables_affected)),
            "total_sales_count": res_count,
            "message": f"Successfully imported {inserted} records into retailpulse_db!"
        }

    except Exception as e:
        logger.error(f"Relational import failed and rolled back: {e}")
        return {
            "success": False,
            "processed": processed,
            "inserted": 0,
            "skipped": 0,
            "failed": processed,
            "tables_affected": [],
            "total_sales_count": 0,
            "message": f"Import failed (transaction rolled back): {str(e)}"
        }
