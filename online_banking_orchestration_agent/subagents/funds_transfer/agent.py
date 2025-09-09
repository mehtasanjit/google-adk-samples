from __future__ import annotations

from typing import Any, Dict, List, Optional

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.agents.callback_context import CallbackContext

import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parents[2] / "data"

def _load_json_file(path: Path) -> Any:
	if not path.exists():
		return None
	with path.open("r", encoding="utf-8") as f:
		return json.load(f)

def _save_json_file(path: Path, data: Any) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=1)

def _load_payees(user_id: str) -> List[Dict[str, Any]]:
	user_dir = DATA_DIR / "users" / user_id
	path = user_dir / "payees.json"
	return _load_json_file(path) or []

def _load_accounts(user_id: str) -> List[Dict[str, Any]]:
	user_dir = DATA_DIR / "users" / user_id
	path = user_dir / "accounts.json"
	return _load_json_file(path) or []

# ---------------------------
# Mock tools for demo
# ---------------------------

# In a real app these would hit SoR APIs. Here we keep it simple and stateless.

# Payees are loaded from centralized data: data/users/<user_id>/payees.json

# Balances will be read via accounts data when needed; keeping placeholders minimal.

def update_session_state(tool_context: ToolContext, key: str, value: str):
    # Print the update of the session state.
    print("INFO: Updating the session state")
    print(f"INFO: Key: {key}, Value: {value}")
    if key.lower().strip() == "user_id":
        tool_context.state["user_id"] = value
        tool_context.state["is_user_id_updated"] = True

def search_payees_by_name_or_alias(tool_context: ToolContext, query: str, user_id: str):
	"""
	Search payees by name or alias. Returns matches (may be empty).
	"""
	q = (query or "").strip().lower()
	resolved_user = user_id
	payees = _load_payees(resolved_user)
	matches = [
		p for p in payees
		if q and (q in p.get("name", "").lower() or any(q in (a or "").lower() for a in p.get("alias", [])))
	]
	return matches


def list_user_payees(tool_context: ToolContext, user_id: str):
	"""
	Return the user's saved payees.
	"""
	resolved_user = user_id
	payees = _load_payees(resolved_user)
	print(payees)
	return payees

def get_account_balance(tool_context: ToolContext, account_id: str, user_id: str):
	"""
	Return available balance for an account, sourced from data/users/<user_id>/accounts.json
	"""
	resolved_user = user_id
	accounts = _load_accounts(resolved_user)
	for acct in accounts:
		if acct.get("account_id") == account_id:
			currency = acct.get("currency", "INR")
			available = acct.get("available_balance")
			if available is None:
				# Fallback to balance when available_balance is absent
				available = acct.get("balance", 0.0)
			return {"status": "OK", "available": float(available or 0.0), "currency": currency}
	return {"status": "NOT_FOUND", "available": 0.0, "currency": "INR"}

# New: validate a provided account_id for the current user
def validate_account_id(tool_context: ToolContext, account_id: str, user_id: str):
	"""
	Validate whether the provided account_id exists for the user.

	Returns a dict:
	- status: "OK" | "NOT_FOUND" | "FAILED"
	- valid: bool (present when status is OK/NOT_FOUND)
	- account: {account_id, type, nickname, currency} (present when valid)
	- candidates: [account_ids...] (present when not found)
	- source: path to accounts.json
	- error: reason (only when status == FAILED)
	"""
	normalized = (account_id or "").strip()
	if not normalized:
		return {"status": "FAILED", "error": "MISSING_ACCOUNT_ID"}

	resolved_user = user_id or (tool_context.state.get("user_id") if tool_context else None)
	if not resolved_user:
		return {"status": "FAILED", "error": "MISSING_USER_ID"}

	user_dir = DATA_DIR / "users" / resolved_user
	path = user_dir / "accounts.json"
	accounts = _load_json_file(path) or []
	match = next((a for a in accounts if a.get("account_id") == normalized), None)
	if not match:
		candidates = [a.get("account_id") for a in accounts if a.get("account_id")]
		return False

	account_summary = {
		"account_id": match.get("account_id"),
		"type": match.get("type"),
		"nickname": match.get("nickname"),
		"currency": match.get("currency", "INR"),
	}
	return True


def initiate_transfer(
	tool_context: ToolContext,
	source_account_id: str,
	payee_id: str,
	amount: float,
	currency: str = "INR",
	reference: Optional[str] = None,
	user_id: Optional[str] = None
) -> Dict[str, Any]:
	"""
	Initiate a transfer, persist it to data/transactions/<account_id>.json, and update accounts.json.
	"""
	if amount <= 0:
		return {"status": "FAILED", "error": "INVALID_AMOUNT"}

	resolved_user = user_id
	accounts = _load_accounts(resolved_user)
	account: Optional[Dict[str, Any]] = None
	for acct in accounts:
		if acct.get("account_id") == source_account_id:
			account = acct
			break
	if not account:
		return {"status": "FAILED", "error": "ACCOUNT_NOT_FOUND"}

	acct_currency = account.get("currency", "INR")
	if currency and acct_currency and currency != acct_currency:
		return {"status": "FAILED", "error": "CURRENCY_MISMATCH"}

	available = account.get("available_balance")
	if available is None:
		available = account.get("balance", 0.0)
	available = float(available or 0.0)
	if amount > available:
		return {"status": "FAILED", "error": "INSUFFICIENT_FUNDS"}

	# Load payee for description/counterparty
	payees = _load_payees(resolved_user)
	payee = next((p for p in payees if p.get("payee_id") == payee_id), None)
	payee_name = payee.get("name") if payee else payee_id

	# Prepare transaction record
	now = datetime.utcnow()
	date_str = now.strftime("%Y-%m-%d")
	transfer_id = f"T-FT-{now.strftime('%Y%m%d%H%M%S')}"
	description = reference or f"Transfer to {payee_name}"
	new_running_balance = available - amount
	transaction = {
		"id": transfer_id,
		"date": date_str,
		"description": description,
		"merchant": None,
		"mcc": None,
		"category": "Transfer",
		"amount": -float(amount),
		"currency": acct_currency or currency or "INR",
		"method": "NEFT",
		"status": "POSTED",
		"running_balance": round(new_running_balance, 2),
		"counterparty": payee_name,
	}

	# Persist to transactions file
	transactions_path = DATA_DIR / "users" / resolved_user / "transactions" / f"{source_account_id}.json"
	existing_txns = _load_json_file(transactions_path) or []
	# Prepend latest transaction to keep newest-first ordering similar to sample files
	updated_txns = [transaction] + list(existing_txns)
	_save_json_file(transactions_path, updated_txns)

	# Update account balances and write back
	account["available_balance"] = round(new_running_balance, 2)
	if account.get("type") != "CREDIT_CARD":
		# For deposit accounts, also reduce ledger balance for demo purposes
		account["balance"] = round(float(account.get("balance", new_running_balance)) - float(amount), 2)
	account["last_updated"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
	_save_json_file(DATA_DIR / "users" / resolved_user / "accounts.json", accounts)

	return transfer_id


search_payees_tool = FunctionTool(func=search_payees_by_name_or_alias)
list_payees_tool = FunctionTool(func=list_user_payees)
get_balance_tool = FunctionTool(func=get_account_balance)
initiate_transfer_tool = FunctionTool(func=initiate_transfer)
update_session_state_tool = FunctionTool(func=update_session_state)
validate_account_id_tool = FunctionTool(func=validate_account_id)

# ---------------------------
# Funds Transfer LLM Agent
# ---------------------------
funds_transfer_agent = LlmAgent(
	name="funds_transfer_agent",
	model="gemini-2.5-flash",
	description=(
		"Funds transfer workflow: capture payee, validate existence, select source account, "
		"check balance, confirm, and initiate the transfer."
	),
	instruction=(
		f"""

		  **Role:**
		    * You are the **Funds Transfer Specialist,** a precise, single-purpose agent. 
			* **Your persona is functional, secure, and direct.** 
			* You **guide the user through a strict, multi-step workflow to safely transfer money.** 
			* You must follow the defined workflow, one step at a time.

		  **Core Objective:**
		    * To execute a **deterministic funds transfer.** 
			* **You must follow the exact sequence of tasks given to you,** collecting and validating each piece of information before moving to the next. 
		
		  **Common Instructions:**
		    * **Keep responses concise:** Only ask for the information needed for your current step.
			* **One Step at a Time:** Do not ask for the payee and the source account in the same turn. Complete each step in sequence.
			* **Set Early Exit:** If any step fails, you must clearly inform the user of the reason, and stop the workflow immediately.
		
		  **Core Directives and Tasks: You must strictly follow the steps below:**
		    * **Step 1: Retrieve User ID:**
			  * Get the User ID from the session state variable {{user_id}}.
			* **Step 2: Capture Payee:**
			  * **Request the user the payee name or alias, and capture the same.**
			  * You must use the **update_session_state_tool, and update the key transfer.payee_name_or_alias, with payee information.**
			* **Step 3: Verify Payee:**
			  * Call the **search_payees_tool, using the value from transfer.payee_name_or_alias, i.e. {{transfer.payee_name_or_alias}}.**
			  * Branching Logic:
			    * If **no match is found: Strictly follow the steps below:**
				  * **Inform the user.**
				  * **You must call** the **list_payees_tool tool, to retrieve the list of payees.**
				  * **You must output the list of payees, retrieved from the list_payees_tool.**
				* If **match is found: Strictly follow the steps below:**
				  * **Confirm the match with the user, and wait for the user to confirm.**
				  * Update user confirmation using **update_session_state_tool, with key as transfer.payee_confirmed, and value as True, or False, based on the user's confirmation.**
			* **Step 4: Capture Source Account:**
			  * Ask the user for the **account_id from which funds must be transferred.**
			  * Capture **the user input in session state, using key transfer.account_id, and value as the user provided account_id.**
			* **Step 5: Validate Source Account ID:**
			  * Use the **validate_account_id_tool, using the value from transfer.account_id, i.e. {{transfer.account_id}}.**
			  * Branching Logic:	
			    * If **status is NOT_FOUND: Strictly follow the steps below:**
				  * **Inform the user.**
				* If **status is OK: Strictly follow the steps below:**
				  * **Confirm the match with the user, and wait for the user to confirm.**
				  * Update user confirmation using **update_session_state_tool, with key as transfer.account_confirmed, and value as True, or False, based on the user's confirmation.**
			* **Step 6: Check Balance:**
			  * Call the **get_balance_tool, using the value from transfer.account_id, i.e. {{transfer.account_id}}.**
			  * Branching Logic:
			    * If **available balance is insufficient, inform the user.**
			* **Step 7: Confirm Transfer:**
			  * **Ask the user for confirmation to proceed with the transfer.**
			  * **Capture user confirmation using** the **update_session_state_tool, with key as transfer.confirmed, and value as True.**
			* **Step 8: Initiate Transfer:**
			  * Call the **initiate_transfer_tool, using the value from transfer.account_id, i.e. {{transfer.account_id}}, and the value from transfer.payee_id, i.e. {{transfer.payee_id}}.**
			  * Capture the transfer_id using **update_session_state_tool, with key as transfer.transfer_id, and value as the transfer_id.**
			* **Step 9: Output confirmation message:**
			  * **Output the confirmation message, that the transfer has been initiated successfully.**
		"""
	),
	tools=[
		search_payees_tool, 
		list_payees_tool, 
		validate_account_id_tool, 
		get_balance_tool, 
		initiate_transfer_tool, 
		update_session_state_tool
	],
)
