"""
Conversational netbanking agent flow (high-level):

1) Setup
   - Configures Google GenAI/Vertex AI environment variables.
   - Resolves `DATA_DIR` for on-disk user data.

2) User ID validation gates (orchestrator pre-checks)
   - `validate_user_id_before_agent`: runs before the orchestrator agent executes.
     - Gets the `user_id` from state and validates against `DATA_DIR/users/<uid>/accounts.json`.
     - Returns None to continue, or a `types.Content` message to short-circuit with an error surfaced to the model.
   - `validate_user_id_before_model`: runs before the model is called.
     - Performs the same validation but returns an `LlmResponse` to prevent the model call when invalid.

3) Session state + control tools
   - `update_session_state(tool_context, key, value)`: writes to `tool_context.state` and flags `is_user_id_updated=True`.
   - `before_user_id_model_callback`: skips `user_id_agent` once the user ID has already been updated.
   - `add_session_to_memory`: tool to persist the current session into long-term memory when the orchestrator decides.
   - `load_memory`: tool available to recall prior sessions if needed by the orchestrator.

4) Agents
   - `user_id_agent`: collects `user_id` from the user and updates session state via `update_session_state_tool`.
     - Has an after-agent wait (`wait_for_sync`) and a guard to skip if already updated.
     - Defined here but not wired into `root_agent` in this file.
   - `orchestrator_agent`: root coordinator for intents (accounts/advisor/funds transfer) and general Q&A.
     - Reads `user_id` from session state, can set `descriptive_summary`, and can call memory tools.
     - Uses both validation callbacks to ensure a valid `user_id` before model invocation.
     - Delegates to sub-agents: `accounts_agent`, `advisor_agent`, `funds_transfer_agent`.
   - `root_agent` (`SequentialAgent`): runs the single step `orchestrator_agent`.

5) Turn lifecycle (typical)
   - Request enters `orchestrator_agent` to `validate_user_id_before_agent` to `validate_user_id_before_model`.
   - If validation fails, a message is returned early; otherwise, the model runs with the orchestrator instruction.
   - The orchestrator may update session flags, call tools (`load_memory`, `adk_add_session_to_memory_tool`, `update_session_state_tool`),
     and/or delegate to sub-agents based on the user's intent.
"""
import os

os.environ["GOOGLE_CLOUD_PROJECT"] = ""
os.environ["GOOGLE_CLOUD_LOCATION"] = ""
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = ""

from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from google.adk.tools import load_memory, FunctionTool # built-in memory retrieval tool
from .subagents import accounts_agent, advisor_agent_bundle, funds_transfer_agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from pathlib import Path
import re
import time
from typing import Optional, Dict, Any
from google.adk.models import LlmResponse, LlmRequest
from google.genai import types

DATA_DIR = Path(__file__).parent / "data"

def validate_user_id_before_agent (callback_context: CallbackContext) -> Dict[str, Any]:
    """Validate a user_id by format and presence of user data on disk.

    Resolution order for user_id:
    1) explicit function arg
    2) tool_context.state["user_id"] if ToolContext provided

    Returns a dict like {"valid": bool, "reason": <str_if_invalid>}.
    """

    is_user_id_updated = callback_context.state.get("is_user_id_updated", False)

    if not callback_context.state.get("is_user_id_updated"):
        return LlmResponse(
            content=types.Content(
                role="user",
                parts=[types.Part(
                    text=f""
                )]
            )
        )

    def _is_valid_user_id_format(uid: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,31}", uid or ""))
    
    uid = callback_context.state.get("user_id")
    
    print(f"INFO: Validating user_id: {uid}")
    
    is_valid = True
    reason = ""

    if not uid:
        is_valid = False
        reason = "MISSING"
    if not _is_valid_user_id_format(uid):
        is_valid = False
        reason = "INVALID_FORMAT"

    if is_valid:
      user_dir = DATA_DIR / "users" / uid
      if not user_dir.exists():
          is_valid = False
          reason = "USER_NOT_FOUND"
      if not (user_dir / "accounts.json").exists():
          is_valid = False
          reason = "ACCOUNTS_NOT_FOUND"

    if is_valid:
        print("INFO: User ID is valid. Continuing with the conversation.")
        return None
    else:
        return types.Content(
            role="user",
            parts=[types.Part(
                text=f"User ID: The user ID {uid} is not valid. Reason: {reason}."
            )]
        )

def validate_user_id_before_model (callback_context: CallbackContext, llm_request: LlmRequest) -> Dict[str, Any]:
    """Validate a user_id by format and presence of user data on disk.

    Resolution order for user_id:
    1) explicit function arg
    2) tool_context.state["user_id"] if ToolContext provided

    Returns a dict like {"valid": bool, "reason": <str_if_invalid>}.
    """
    
    is_user_id_updated = callback_context.state.get("is_user_id_updated", False)

    if not callback_context.state.get("is_user_id_updated"):
        return LlmResponse(
            content=types.Content(
                role="user",
                parts=[types.Part(
                    text=f""
                )]
            )
        )
        
    def _is_valid_user_id_format(uid: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,31}", uid or ""))

    uid = callback_context.state.get("user_id")
    
    print(f"INFO: Validating user_id: {uid}")
    
    is_valid = True
    reason = ""

    if not uid:
        is_valid = False
        reason = "MISSING"
    if not _is_valid_user_id_format(uid):
        is_valid = False
        reason = "INVALID_FORMAT"

    if is_valid:
      user_dir = DATA_DIR / "users" / uid
      if not user_dir.exists():
          is_valid = False
          reason = "USER_NOT_FOUND"
      if not (user_dir / "accounts.json").exists():
          is_valid = False
          reason = "ACCOUNTS_NOT_FOUND"

    if is_valid:
        print("INFO: User ID is valid. Continuing with the conversation.")
        return None
    else:
        return LlmResponse(
            content=types.Content(
                role="user",
                parts=[types.Part(
                    text=f"User ID: The user ID {uid} is not valid. Reason: {reason}."
                )]
            )
        )

def update_session_state(tool_context: ToolContext, key: str, value: str):
    # Print the update of the session state.
    print("INFO: Updating the session state")
    print(f"INFO: Key: {key}, Value: {value}")
    if key.lower().strip() == "user_id":
        tool_context.state["user_id"] = value
        tool_context.state["is_user_id_updated"] = True

def before_user_id_model_callback (callback_context: CallbackContext, llm_request: LlmRequest):
    updated_flag = callback_context.state.get("is_user_id_updated")
    if updated_flag:
        return LlmResponse(
            content=types.Content(
                role="user",
                parts=[types.Part(
                    text=f"The user ID is already updated. Skipping this agent."
                )]
            )
        )
    else:
        return None

async def add_session_to_memory(tool_context: ToolContext):
    """
    Tool: add_session_to_memory_tool

    Adds the current session to the user's memory using the configured MemoryService.
    This enables new information from the current conversation to be immediately available
    for recall in future turns. Use this tool when you determine that the current context
    or information should be persisted as part of the user's long-term memory.

    Args:
        tool_context (ToolContext): The context object containing invocation and session info.

    Returns:
        None
    """
    await tool_context._invocation_context.memory_service.add_session_to_memory(
        session=tool_context._invocation_context.session
    )

def exit_loop(tool_context: ToolContext):
  """Call this function ONLY when the user_id is confirmed, signaling the iterative process should end."""
  print(f"[Tool Call] exit_loop triggered by {tool_context.agent_name}")
  tool_context.actions.escalate = True
  # Return empty dict as tools should typically return JSON-serializable output
  return {}

def wait_for_sync (callback_context: CallbackContext):
    time.sleep(3)

adk_add_session_to_memory_tool = FunctionTool(add_session_to_memory)
update_session_state_tool = FunctionTool(update_session_state)

# Agent to get the user_id from the user.
user_id_agent = LlmAgent (
    name="user_id_agent",
    model="gemini-2.5-flash",
    description="Agent to get the user_id from the user",
    instruction=(
        f"""
          **Role:**
            * **You are a user_id agent. You are responsible for getting the user_id from the user.**
          
          **Core directives:**
            * **Thoroughly, and meticulously review and understand the user query to identify, and extract the User ID provided by the user.**
            * **You must update the session state variable with key as "user_id" and value as the user_id provided by the user,** using the **update_session_state_tool**.
        """
    ),
    tools=[update_session_state_tool],
    after_agent_callback=wait_for_sync,
    before_model_callback=before_user_id_model_callback
)

# Root coordinator agent for conversational netbanking.
orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model="gemini-2.5-flash",
    description=(
        f"""
          Root netbanking coordinator that interprets intents and, 
          can delegate account-related queries to the Accounts agent, 
          portfolio questions to the Advisor, 
          and payments to the Funds Transfer agent.
        """
    ),
    instruction=(
      f"""
        **Role:**
          * You are the coordinator for netbanking, for one of the major Indian banks.
          * Your persona is professional, helpful, and efficient, acting as the primary point of contact for all users.
          
        **Objective, or core directive:**
          * Your **primary objective is to function as an intelligent coordinator.**
          * Your **core directive is to first accurately understand a user's request and then either resolve it directly if it's a general query, or delegate it to the appropriate specialized agent.**
        
        **Common Instructions:**
          * Keep your answers concise, brief, and to the point.

        **Tasks, or Workflow: You must strictly to the workflow defined below.**
          * **Step 1: User Identification:**
            * You must first get the user_id from the session state variable user_id. User ID is {{user_id}}.
            * This step is mandatory before proceeding.
          * **Step 2: Intent analysis, and preference handling:**
            * Step 2.1: **Parse and understand user intent:**
              **You must unambiguously understand, and parse the user intent to understand their primary goal.**
            * Step 2.2: **Update preferences:**
              * **If the user wants a descriptive summary of the accounts,** use the **update_session_state_tool** to update the session state variable with key as "descriptive_summary" and value as True.
          * **Step 3: **Recall from memory:**
              * You must call the **load_memory** tool, to load **user preferences, and historical context.**
              * You must **use the retrieved memory to fully understand, inform, and align your handling of the user's query.**
              * **Critical note: Prioritize the Current Request:** If **there is any conflict between preferences, and / or context loaded from memory and an explicit instruction in the user's query, the user query always supersedes the information retrieved from memory.**
          * **Step 4: Scoped Request Handling & Routing:**
            * **Handle General Inquiries Directly:** Your scope is limited to the handling, and responding to general questions. If the request is a general question, answer it yourself.
            * **Handling Delegation:**
              * **Delegate Account Queries:** For **requests about account details, balances, statements, transactions, you must delegate to the accounts_agent.**
              * **Delegate Investment, and / or advisory Queries:** For requests **about financial advice or portfolios, you must delegate to the advisor_agent.**
              * **Delegate Fund Transfer Queries:** For requests **involving moving money, or money movement, you must delegate to the funds_transfer_agent.**
            * **Critical Delegation Handling:**
              * **Delegation agents may require multiple turns to complete.**
              * **Ensure that you continue the conversation seamlessly, unless there is a change in the user intent.**
          * **Step 5: Intelligent Memory Creation:**
            * **You must proactively identify and save key pieces of information,** that could be **useful in future conversations, using the adk_add_session_to_memory_tool tool.**
            * **Strict Exceptions:**
              * You must **strictly never add the user_id to the memory.**
      """
    ),
    sub_agents=[accounts_agent, advisor_agent_bundle, funds_transfer_agent],
    tools=[load_memory, adk_add_session_to_memory_tool, update_session_state_tool],
    before_model_callback=validate_user_id_before_model,
    before_agent_callback=validate_user_id_before_agent
)

root_agent = SequentialAgent (
    name="root_agent",
    description="Root agent for the overall workflow.",
    sub_agents=[
        user_id_agent,
        orchestrator_agent
    ]
)
