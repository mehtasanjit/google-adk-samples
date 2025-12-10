import json
import os
from datetime import datetime

DATA_DIR = "/usr/local/google/home/sanjitmehta/work/cred-all/data"

def get_user_data_dir(user_id):
    return os.path.join(DATA_DIR, user_id)

def validate_user_id(user_id):
    return os.path.exists(get_user_data_dir(user_id))

def read_json_file(file_path):
    if not os.path.exists(file_path):
        # print(f"DEBUG: File not found: {file_path}")
        return None
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON from {file_path}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error reading {file_path}: {e}")
        return None

def get_profile(user_id):
    path = os.path.join(get_user_data_dir(user_id), "profile.json")
    return read_json_file(path)

def get_bank_accounts(user_id):
    path = os.path.join(get_user_data_dir(user_id), "bank_accounts.json")
    return read_json_file(path) or []

def get_bank_account_transactions(user_id, start_date=None, end_date=None, categories=None, account_ids=None, min_amount=None, max_amount=None, payment_mediums=None):
    path = os.path.join(get_user_data_dir(user_id), "bank_account_transactions.json")
    transactions = read_json_file(path) or []
    
    filtered_transactions = []
    for txn in transactions:
        txn_date = datetime.strptime(txn["date"], "%Y-%m-%d")
        
        if start_date and txn_date < datetime.strptime(start_date, "%Y-%m-%d"):
            continue
        if end_date and txn_date > datetime.strptime(end_date, "%Y-%m-%d"):
            continue
        if categories and txn["category"] not in categories:
            continue
        if account_ids and txn["account_id"] not in account_ids:
            continue
        if min_amount and txn["amount"] < min_amount:
            continue
        if max_amount and txn["amount"] > max_amount:
            continue
        if payment_mediums and txn.get("payment_medium") not in payment_mediums:
            continue
        
        filtered_transactions.append(txn)
    
    return filtered_transactions

def get_credit_card_transactions(user_id, start_date=None, end_date=None, categories=None, account_ids=None, min_amount=None, max_amount=None, payment_mediums=None):
    path = os.path.join(get_user_data_dir(user_id), "credit_card_transactions.json")
    transactions = read_json_file(path) or []
    
    filtered_transactions = []
    for txn in transactions:
        txn_date = datetime.strptime(txn["date"], "%Y-%m-%d")
        
        if start_date and txn_date < datetime.strptime(start_date, "%Y-%m-%d"):
            continue
        if end_date and txn_date > datetime.strptime(end_date, "%Y-%m-%d"):
            continue
        if categories and txn["category"] not in categories:
            continue
        if account_ids and txn["account_id"] not in account_ids:
            continue
        if min_amount and txn["amount"] < min_amount:
            continue
        if max_amount and txn["amount"] > max_amount:
            continue
        if payment_mediums and txn.get("payment_medium") not in payment_mediums:
            continue
        
        filtered_transactions.append(txn)
    
    return filtered_transactions

def get_mutual_funds(user_id):
    path = os.path.join(get_user_data_dir(user_id), "user_mutual_funds.json")
    return read_json_file(path) or []

def get_mutual_fund_transactions(user_id):
    path = os.path.join(get_user_data_dir(user_id), "user_mutual_fund_transactions.json")
    return read_json_file(path) or []

def get_sip_plans(user_id):
    path = os.path.join(get_user_data_dir(user_id), "user_sip.json")
    return read_json_file(path) or []

def get_credit_cards(user_id):
    path = os.path.join(get_user_data_dir(user_id), "user_credit_cards.json")
    return read_json_file(path) or []

def get_credit_card_payments(user_id, card_id=None):
    path = os.path.join(get_user_data_dir(user_id), "user_credit_card_payments.json")
    payments = read_json_file(path) or []
    if card_id:
        return [p for p in payments if p["card_id"] == card_id]
    return payments

def get_stock_holdings(user_id):
    path = os.path.join(get_user_data_dir(user_id), "user_stocks.json")
    return read_json_file(path) or []

def get_stock_transactions(user_id):
    path = os.path.join(get_user_data_dir(user_id), "user_stock_transactions.json")
    return read_json_file(path) or []

def get_fd_rates():
    """Returns the current FD interest rates."""
    path = os.path.join(DATA_DIR, "common", "fd_rates.json")
    return read_json_file(path) or []

def get_rd_rates():
    """Returns the current RD interest rates."""
    path = os.path.join(DATA_DIR, "common", "rd_rates.json")
    return read_json_file(path) or []
