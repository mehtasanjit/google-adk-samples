This folder contains a small multi-agent netbanking demo built on Google ADK. It includes:
- `root_agent` (Sequential): coordinates the overall flow
- `orchestrator_agent` (LLM): intent understanding + routing
- `user_id_agent` (LLM): collects and stores `user_id` in session state
- `accounts_agent` (LLM + tools): balances, accounts, transactions
- `advisor_agent_bundle` (Sequential):
  - `AdvisoryEnrolmentCheckAgent` (Custom): sets `advisory.enrolled` in session state
  - `advisor_agent` (LLM + tools): portfolio summaries and guidance
- `funds_transfer_agent` (LLM + tools): payees, account validation, balance check, confirmation, transfer

Data fixtures live under `data/users/<your_user_id>/`.

## Quick reference
- Main entry: `agent.py` — defines `root_agent`
- Subagents: `subagents/`
- User data folder structure (create per user_id):
  - `data/users/<your_user_id>/accounts.json` (required)
  - `data/users/<your_user_id>/transactions/` (optional per account)
  - `data/users/<your_user_id>/payees.json` (funds transfer)
  - `data/users/<your_user_id>/portfolio.json` (advisor)
  - `data/users/<your_user_id>/advisory.json` with `{ "enrolled": true|false }` (advisor)

## Prerequisites
- Python 3.10+
- Packages (typical):
```bash
pip install "google-cloud-aiplatform[adk,agent_engines]" google-adk google-genai
```
- Environment (example):
```bash
export GOOGLE_CLOUD_PROJECT=[Your GCP Project]
export GOOGLE_CLOUD_LOCATION=[Your GCP Location]
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

## Testing: User ID validation
User ID validation is enforced twice around the orchestrator:
- `validate_user_id_before_agent`
- `validate_user_id_before_model`

Behavior:
- If `session.state["is_user_id_updated"]` is not set/False, the orchestrator step is short-circuited and the system asks for a user ID.
- Once `user_id_agent` sets `session.state["user_id"]` and `session.state["is_user_id_updated"] = True`, subsequent turns proceed normally.

How to test:
1) Ensure you have created `data/users/<your_user_id>/accounts.json`.
2) Start a new session without `user_id` in state and send any request (e.g., "What are my balances?").
   - Expected: System requests a user ID (or `user_id_agent` runs first in the sequential root).
3) Provide your user ID (the folder you created in step 1).
   - Expected: Validation passes if `accounts.json` exists for that user.
4) Next request in the same session should skip user-id collection (due to `is_user_id_updated=True`).

## Testing: Descriptive vs. non-descriptive summaries
The orchestrator captures a preference flag `descriptive_summary` via `update_session_state_tool`. The `accounts_agent` inspects this in `before_accounts_model_callback` and adjusts output hints.

How to test:
- Ask: "Give me a descriptive summary of my accounts and any notable trends."
  - Expected: `descriptive_summary=True`; `accounts_agent` emits a descriptive output.
- Ask: "List account balances only."
  - Expected: concise listing (no descriptive hints).

## Testing: Advisor enrollment precheck
`advisor_agent_bundle` runs `AdvisoryEnrolmentCheckAgent` before `advisor_agent`.
- The custom agent reads `session.state["user_id"]`, loads `data/users/<your_user_id>/advisory.json`, and writes:
  - `session.state["advisory.enrolled"] = True|False`
  - `session.state["advisory.enrollment_source"] = <path>`
- It yields a small event and returns (no LLM call).

How to test:
1) Ensure your user has `advisory.json` with `{ "enrolled": true }` or `{ "enrolled": false }`.
2) Ask for investment guidance (e.g., "What adjustments would you recommend for my portfolio?").
3) Observe behavior:
   - When enrolled: advisor proceeds with portfolio-grounded guidance.
   - When not enrolled: advisor should state not enrolled and request enrollment before advice.

## Testing: Funds transfer — account_id validation
A dedicated tool `validate_account_id_tool` validates the provided source `account_id` for the current user.

Suggested flow segments (agent instruction mirrors this):
- Capture payee → verify via `search_payees_tool`; present `list_payees_tool` if no match and stop.
- Capture source account → store as `transfer.account_id`.
- Validate source account → call `validate_account_id_tool` with `{{transfer.account_id}}`.
  - If NOT_FOUND: inform user, present their accounts (you can use `accounts_agent`’s `list_accounts_tool`), then stop.
  - If OK: confirm with the user and set `transfer.account_confirmed=True`.
- Check balance → call `get_balance_tool` with `{{transfer.account_id}}`; stop if insufficient.
- Confirm and initiate transfer → call `initiate_transfer_tool` with `{{transfer.account_id}}` and `{{transfer.payee_id}}`.

---

## Testing: Funds Transfer — End-to-End

Prerequisites
- `data/users/<your_user_id>/payees.json` with at least one payee:
```json
[
  { "payee_id": "P001", "name": "John Smith", "alias": ["john", "smith"] }
]
```
- `data/users/<your_user_id>/accounts.json` with at least one source account:
```json
[
  { "account_id": "CHK-1234", "type": "CHECKING", "nickname": "Primary Checking", "currency": "INR", "balance": 50000, "available_balance": 45000 }
]
```

State keys used by the flow
- `transfer.payee_name_or_alias`, `transfer.payee_confirmed`
- `transfer.account_id`, `transfer.account_confirmed`
- `transfer.confirmed`, `transfer.transfer_id`, `transfer.status`

Step-by-step
1) Set/confirm user id
   - Ensure `session.state["user_id"] = <your_user_id>` (use `user_id_agent` in the root sequence).
2) Ask to transfer
   - Example: "Transfer 1,000 INR to John"
3) Payee verification
   - Agent calls `search_payees_tool`. If no match, it presents `list_payees_tool` and stops.
   - If a match is found, it confirms and sets `transfer.payee_confirmed=True`.
4) Capture source account
   - Agent asks for `account_id` and stores it in `transfer.account_id`.
5) Validate account
   - Agent calls `validate_account_id_tool` with `{{transfer.account_id}}`.
   - If NOT_FOUND: agent informs user, lists accounts (use `accounts_agent`’s `list_accounts_tool`), stops.
   - If OK: agent confirms and sets `transfer.account_confirmed=True`.
6) Check balance
   - Agent calls `get_balance_tool`. If insufficient funds, it informs and stops.
7) Confirm transfer
   - Agent asks for confirmation and sets `transfer.confirmed=True`.
8) Initiate transfer
   - Agent calls `initiate_transfer_tool` with the confirmed `account_id` and `payee_id`.
   - Agent records `transfer.transfer_id` and `transfer.status` via `update_session_state_tool`.

Branch testing
- No payee match: use a name not in `payees.json` → expect listing and stop.
- Invalid account_id: provide a non-existing id → expect accounts listing and stop.
- Insufficient funds: provide an amount greater than `available_balance` → expect stop with reason.
- Success path: valid payee, valid account, sufficient funds → expect POSTED status and transfer_id.

Expected side-effects
- A new transaction appended in `data/users/<your_user_id>/transactions/<account_id>.json`.
- Updated balances in `data/users/<your_user_id>/accounts.json` (available/ledger where applicable).

## Troubleshooting
- Missing user data
  - Ensure `data/users/<your_user_id>/accounts.json` exists; validators will block otherwise.
- Agent keeps asking for user ID
  - Confirm `user_id_agent` has set `session.state["user_id"]` and `is_user_id_updated=True`.
- Tools referenced in instructions
  - When listing accounts, use `accounts_agent`’s `list_accounts_tool`.
- Event escalation in custom agents
  - Do not pass `escalate=True` to events; yield a normal `Event` and `return` to end the step.

## References
- Custom agents (Google ADK): [Custom agents | Google ADK docs](https://google.github.io/adk-docs/agents/custom-agents/) 