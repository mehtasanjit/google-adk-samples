from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.agents.callback_context import CallbackContext

import time

DATA_DIR = Path(__file__).parents[2] / "data"

def print_session_state_variables (callback_context: CallbackContext):
	print("INFO: Printing the session state variables")
	print(callback_context.state.to_dict())

def _load_json_file(path: Path) -> Any:
	if not path.exists():
		return None
	with path.open("r", encoding="utf-8") as f:
		return json.load(f)

def before_accounts_model_callback (callback_context: CallbackContext):
	descriptive_summary_flag = callback_context.state.get("descriptive_summary")
	if descriptive_summary_flag:
		callback_context.state["accounts_agent_output_hints"] = f"""
		  You must output a descriptive summary of the accounts, with perhaps some financial advice.
		"""
	else:
		callback_context.state["accounts_agent_output_hints"] = f"""
		  No output hints.
		"""
	print (f"INFO: call back context is - {callback_context.state.to_dict()}")
	time.sleep(1)

# ---------------------------
# Function tools (JSON-backed)
# ---------------------------

def list_accounts(user_id: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
	"""
	List the bank accounts for a given user from JSON files.

	Parameters:
	  user_id: The identifier for the banking user.

	Returns:
	  A dict with keys:
		- status: "OK"
		- accounts: list of {account_id, type, currency, balance, nickname, ...}
		- source: where the data came from
	"""
	user_dir = DATA_DIR / "users" / user_id
	accounts_path = user_dir / "accounts.json"
	accounts_data: Optional[List[Dict[str, Any]]] = _load_json_file(accounts_path)
	if not accounts_data:
		return {"status": "OK", "accounts": [], "source": str(accounts_path)}
	return {"status": "OK", "accounts": accounts_data, "source": str(accounts_path)}


def get_recent_transactions(
	account_id: str,
	days: int,
	user_id: Optional[str] = None,
	tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
	"""
	Return recent transactions for an account over a given window from JSON files.

	Parameters:
	  account_id: Target account identifier (e.g., "CHK-1234").
	  days: Number of days to look back (e.g., 30).
	  user_id: Optional explicit user identifier. If not provided, resolved from ToolContext.state.

	Returns:
	  A dict with keys:
		- status: "OK"
		- transactions: list of {date, description, category, amount, currency, ...}
		- source: where the data came from
	"""
	resolved_user = user_id or (tool_context.state.get("user_id") if tool_context else None)
	transactions_dir = DATA_DIR / "users" / resolved_user / "transactions"
	transactions_path = transactions_dir / f"{account_id}.json"
	transactions: Optional[List[Dict[str, Any]]] = _load_json_file(transactions_path) or []

	# Filter by date range if dates are present
	cutoff = datetime.utcnow().date() - timedelta(days=days)
	filtered: List[Dict[str, Any]] = []
	for txn in transactions:
		date_str = txn.get("date")
		try:
			if date_str:
				txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
				if txn_date >= cutoff:
					filtered.append(txn)
			else:
				filtered.append(txn)
		except Exception:
			filtered.append(txn)

	return {"status": "OK", "transactions": filtered, "source": str(transactions_path)}


list_accounts_tool = FunctionTool(func=list_accounts)
get_recent_transactions_tool = FunctionTool(func=get_recent_transactions)

# ---------------------------
# Accounts LLM Agent
# ---------------------------
accounts_agent = LlmAgent(
	name="accounts_agent",
	model="gemini-2.5-flash",
	description=(
		"Accounts specialist for balances, account listings, and recent transactions."
	),
	instruction=(
		f"""
		  **Role:**
		    * You are the Accounts specialist.
		
		  **Core directives:**
		    * When the user asks about balances, accounts, or recent activity, use the provided tools to retrieve data.
			* You must first find the User ID from session state variable. User ID is {{user_id}}.
			* Then you must output a statement - "Fetching data for User ID: {{user_id}}".
			* Finally, you must use the provided tools to fulfill user request.
			* Summarize results succinctly and include account nicknames and currencies, as applicable.
		  
		  **Output Hints:** 
		    * Check the session state variable {{accounts_agent_output_hints}}. If hints are provided, output accordingly.
			* If there are "No output hints", output as a well formatted list.
		"""
	),
	tools=[list_accounts_tool, get_recent_transactions_tool],
	before_agent_callback=[before_accounts_model_callback, print_session_state_variables]
)
