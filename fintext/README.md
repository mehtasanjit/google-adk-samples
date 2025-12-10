# FinText Agent System

## Overview
FinText is a sophisticated financial assistant agent designed for **FinCorp**, a fintech platform offering banking, credit cards, stocks, and mutual fund services. It acts as a central orchestrator that intelligently routes user queries to specialized sub-agents or handles them directly using a planned workflow.

## Architecture
The system uses a **Sequential Agent** architecture for its core orchestration, ensuring a strict and reliable flow for every user interaction:

1.  **FinText Orchestrator (`root_agent`)**: The top-level `SequentialAgent` that manages the lifecycle of a request.
    *   **Step 1: Planner (`fintext_planner_agent`)**: Analyzes the user's query, checks authentication, and generates a strict, step-by-step JSON workflow. It handles trivial queries (e.g., "Hello") with single-step plans.
    *   **Step 2: Executor (`fintext_workflow_execution_agent`)**: Retrieves the stored workflow and executes it step-by-step, coordinating with sub-agents and tools.

### Data Agent Pattern
The system employs a **UX-Data Agent** pattern to separate concerns and ensure robustness:
*   **UX Agents (e.g., `banking_agent`)**: Responsible for understanding user intent, managing conversation flow, and synthesizing final natural language responses. They do **not** access data directly.
*   **Data Agents (e.g., `banking_data_agent`)**: Responsible for executing tools, fetching raw data, and returning structured output (JSON/CSV). They are deterministic, focused on data accuracy, and do not generate conversational filler.
    *   *Benefit*: This separation prevents "hallucination" by ensuring the UX agent only speaks based on structured data provided by the Data Agent.

### Sub-Agents
The system delegates domain-specific tasks to specialized sub-agents:
*   **Banking Agent**: Handles FinCorp Bank accounts, balances, and transactions.
*   **Credit Card Agent**: Manages credit card details, payments, and transaction history.
*   **Stocks Agent**: Tracks stock holdings and transactions.
*   **Mutual Funds Agent**: Manages mutual fund portfolios.
*   **Money Agent**: Provides cross-domain financial analysis and insights.
*   **Portfolio News Impact Analysis Agent**: Analyzes how news events might affect the user's portfolio.

## Key Features
*   **Strict Authentication**: Mandatory login check (`check_login_status`) is the first step of every plan.
*   **Explicit Planning**: Every action is pre-planned by the Planner agent to prevent hallucination and ensure safety.
*   **Domain Boundaries**: Agents are strictly scoped to their specific domains (e.g., Banking Agent cannot answer Stock questions).
*   **Trivial Query Handling**: Optimized path for greetings and simple interactions.

## Setup & Usage

### Prerequisites
*   Python 3.10+
*   Google Cloud Project with Vertex AI enabled
*   `google-adk` and other dependencies installed

### Environment Variables
Ensure a `.env` file exists in this directory or environment variables are set:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

### Running the Agent
To start the interactive CLI:
```bash
python3 src/agents/fintext/agent.py
```

## Directory Structure
*   `agent.py`: Main entry point, defines `root_agent`, `fintext_planner_agent`, and `fintext_workflow_execution_agent`.
*   `planner.py`: Custom `FinTextPlanner` class (if used separately, though currently integrated into `agent.py`).
*   `dataops.py`: Utility functions for data retrieval and validation.
*   `subagents/`: Directory containing all specialized sub-agent definitions.
