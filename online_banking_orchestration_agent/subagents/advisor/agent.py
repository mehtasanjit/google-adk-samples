from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.adk.agents import LlmAgent, BaseAgent, SequentialAgent
from google.adk.events import Event
from google.adk.tools import FunctionTool, ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

DATA_DIR = Path(__file__).parents[2] / "data"

def _load_json_file(path: Path) -> Any:
	if not path.exists():
		return None
	with path.open("r", encoding="utf-8") as f:
		return json.load(f)

# ---------------------------
# Function tools (advisor)
# ---------------------------

def get_portfolio_summary(user_id: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
	"""
	Return a current portfolio summary for a user from JSON.
	"""
	user_dir = DATA_DIR / "users" / user_id
	path = user_dir / "portfolio.json"
	portfolio = _load_json_file(path) or {}
	return {"status": "OK", "portfolio": portfolio, "source": str(path)}


get_portfolio_summary_tool = FunctionTool(func=get_portfolio_summary)


def check_advisory_enrollment(user_id: str) -> Dict[str, Any]:
	"""
	Return whether the user is enrolled in advisory services from JSON.
	"""
	user_dir = DATA_DIR / "users" / user_id
	path = user_dir / "advisory.json"
	data = _load_json_file(path) or {}
	enrolled = bool(data.get("enrolled", False))
	return {"status": "OK", "enrolled": enrolled, "source": str(path)}

check_advisory_enrollment_tool = FunctionTool(func=check_advisory_enrollment)

class AdvisoryEnrolmentCheckAgent (BaseAgent):

	async def _run_async_impl (self, ctx: InvocationContext):
		print (f"INFO: [{self.name}] Starting advisory enrolment check.")
		user_id = ctx.session.state["user_id"]
		if not user_id:
			ctx.session.state["advisory.enrolled"] = False
			ctx.session.state["advisory.enrollment_error"] = "MISSING_USER_ID"
			# Termination of this custom agent step
			yield Event(
				author=self.name,
				content=types.Content(role="assistant", parts=[types.Part(text=f"INFO: Client advisory check done. Client enrollment status - {ctx.session.state["advisory.enrolled"]}")])
			)
			# Time to sync.
			time.sleep(1)
			return
		
		result = check_advisory_enrollment(user_id=user_id)
		ctx.session.state["advisory.enrolled"] = bool(result.get("enrolled", False))
		ctx.session.state["advisory.enrollment_source"] = result.get("source", "")
		
		print (f"INFO: Session state - advisory.enrolled = {ctx.session.state["advisory.enrolled"]}")
		# Termination of this custom agent step
		yield Event(
			author=self.name,
			content=types.Content(role="assistant", parts=[types.Part(text=f"INFO: Client advisory check done. Client enrollment status - {ctx.session.state["advisory.enrolled"]}")])
		)
		# Time to sync.
		time.sleep (1)
		return

# ---------------------------
# Advisor LLM Agent
# ---------------------------
advisor_agent = LlmAgent(
	name="advisor_agent",
	model="gemini-2.5-flash",
	description=(
		"Financial advisor for portfolio summaries and contextual guidance."
	),
	instruction=(
		f"""
		  **Role:**
		    * You are **the financial advisor,** a **specialized sub-agent for a major Indian bank.** 
		    * Your **sole focus is on analyzing a user's financial portfolio to provide situational guidance and explain financial concepts.** 
		    * You are **analytical, data-driven, and cautious.**
		
		  **Core objective:**
		    * To provide **dynamic, data-grounded analysis of a user's portfolio in direct response to their question.** 
			* Your **guidance must be based only on the retrieved data and the current session context, never on generic templates.**
		
		  **Inputs:
		    * User Query: The specific question the user asked.
			* Session Context: The prior conversation history leading to this request.
		
		  **Core Directives and Tasks:**
		    * **Strict pre-validation: You must pre-validate if the user is enrolled for advisory services.**
		      * First, **read and confirm the User ID. User ID is {{user_id}}.**
			  * Second, **you must check the latest value of the state variable {{advisory.enrolled}}, to ensure that the user is enrolled into advisory services.
			    * **If {{advisory.enrolled}} is True, then you must continue with giving financial advice.**
				* **If {{advisory.enrolled}} is False, then you must mention that the client is not enrolled, and respectfully request the client to enroll for financial advisory services.**
			* **Strictly mandatory data retrieval: Your must call the get_portfolio_summary tool. All subsequent analysis must be grounded in the data returned from this tool. Do not answer without this data.**
			* **Formulate Response: Synthesize the tool's data with the user's query. Your response must:**
			  * Be concise and directly address the user's need.
			  * Be **generated fresh. Do not use historical context, outputs, and / or templates.**
			
		  **Output Format: You must strictly follow the following output format.**
			  * You **must conclude every single response with a clear disclaimer defined below:**
			    * **Please note that this is a data-driven analysis based on your portfolio and not official financial advice.**

	"""),
	tools=[get_portfolio_summary_tool]
)

advisor_agent_bundle = SequentialAgent (
	name="advisor_agent_bundle",
	description=("Advisory agent bundle"),
	sub_agents=[
		AdvisoryEnrolmentCheckAgent (
			name="advisory_enrolment_check_agent", 
			description="Custom agent to check on advisory ennrolment"
		),
		advisor_agent
	]
)
