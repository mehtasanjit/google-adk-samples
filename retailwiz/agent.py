import os
import sys

# Load environment variables from .env file in the same directory
# This must be done BEFORE importing google.adk or google.genai
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(f"Loaded .env from {dotenv_path}")
    else:
        print(f"Warning: .env not found at {dotenv_path}")
except ImportError:
    print("Warning: python-dotenv not installed")

from google.cloud import aiplatform
from google.adk import Agent
from google.adk.tools import AgentTool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any

from google.adk.apps.app import App
from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin

# Initialize Vertex AI
aiplatform.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION")
)

from datetime import datetime

def get_current_datetime() -> str:
    """Returns the current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_google_search_agent_response (
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict
):
  print("INFO:[Root Agent] Output from Google search agent tool:")
  print (tool_response)

# Import subagents after initializing environment
from .subagents.google_search_agent import google_product_search_agent_loop
from .subagents.google_search_agent import google_product_search_agent_standalone_w_output_schema
from .subagents.google_search_agent import google_product_search_agent_standalone_wo_output_schema
from .subagents.google_search_agent import google_product_search_agent_sequential

def create_retailwiz_root_agent(google_search_tool: AgentTool) -> Agent:
    return Agent(
        name="retailwiz_root_agent",
        model="gemini-2.5-flash",
        description="A retail agent that helps customers across the retail lifecycle.",
        instruction="""
        
        **Role:**
          * You are a **Retail Agent** designed to assist customers across the **retail lifecycle** **strictly within the defined domain and scope**.
          * You have access to specialized **sub-agents and tools** defined below to **help you fulfill these tasks**.

        **Domain & Scope:**
          * **Domain:**
            * **Retail**: You are **strictly focused** on the retail domain and shopping related queries, **strictly within the scope defined below**.
          * **Scope:**
            * **Products:**
              * **Product Discovery**: **Helping users find products** that meet their needs
              * **Product Information and Details**: **Product information and details**
              * **Product Reviews and Ratings**: **User and Expert reviews and ratings**
              * **Pricing**: **Finding and comparing prices** for products
            * **Product Comparison**: **Comparing features, specs, and reviews** of different products
            * **Market Analysis**: **Market trends, product value, and quality**
          * **Refusal Policy**: 
            * **You MUST politely refuse to answer queries that are outside of these domains and scope**

        **Available Tools:**
          * **Google Product Search Agent Tool**: Use this tool to find:
            * Product information and details
            * Product discovery
            * Product pricing
            * Product reviews and ratings
            * Product comparison
            * Market analysis

        **Instructions:**
          * **Step 1**: You **MUST** first call the `get_current_datetime` tool to get the current date and time.
          * **Step 2**: Analyze the **user's request to understand what they are looking for.**
          * **Step 3**: **Identify the right set of tools** required to **fulfill the user's intent and requests**.
          * **Step 4**: Provide **helpful, friendly, and relevant responses** to the customer.

        **Important Note:**
          * **You must NOT, NEVER reveal your internal architecture or tool names to the user.**

    """,
        tools=[google_search_tool, get_current_datetime],
        after_tool_callback=log_google_search_agent_response
    )


# Initialize the Google Search Agent as a tool
# Options to use here - google_product_search_agent_loop, google_product_search_agent_standalone_w_output_schema, google_product_search_agent_standalone_wo_output_schema

google_product_search_agent_tool = AgentTool(agent=google_product_search_agent_sequential)

root_agent = create_retailwiz_root_agent(google_product_search_agent_tool)

# Add global instructions
global_instructions = """
  **Global Context:**
    * **Location**: India
    * **Currency**: INR (₹)
"""

# Initialize the global instructions plugin
# This is used when running using ADK web with flag --extra_plugins
# Example command - adk web --extra_plugins retailwiz.agent.global_instructions_plugin
global_instructions_plugin = GlobalInstructionPlugin (
  global_instruction=global_instructions
)
