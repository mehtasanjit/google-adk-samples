# Multi-Agent System Design Guidelines

**Designing Layered Agentic Systems with ADK**

This document provides a structured way to design and orchestrate multi-agent AI systems, specifically within the Google Agent Development Kit (ADK) ecosystem. It:

* Aligns with official Google Cloud **multi-agent architecture patterns**.
* Introduces a clear separation between **UX agents** and **Data/Worker agents**.
* Explains **why a layered architecture is preferable** to a single “god orchestrator with all tools”.
* Provides **concrete prompt templates** for key agents (Orchestrator, Money Agent, Banking UX, Banking Data).

---

## Abstract

Naïve multi-agent design often starts with a **single orchestrator** that directly calls all tools and services. This works for simple prototypes, but breaks down as:

* Domains multiply (Banking, Credit, Investments, Fraud, etc.),
* Journeys become multi-turn and domain-specific,
* Teams and compliance requirements enter the picture.

This guide shows how to evolve from a **flat tool-attached orchestrator** to a **layered multi-agent architecture**:

* **Orchestrator / Main UX** as the brain.
* **UX agents** for domain-specific conversational experiences.
* **Data/Worker agents** as internal domain services (accessing tools/APIs).
* Clear criteria for **Agent-as-Tool vs Sub-agent transfers**.
* Prompt patterns that avoid “scope clarification loops” when agents call each other.

---

## 1. Motivation: Why Not Just Attach Everything to the Orchestrator?

A common starting point:

> “We have an orchestrator agent. Let’s just attach every tool and every data source to it: banking tools, credit tools, MF tools, fraud, movement, search, everything. The orchestrator can figure it out.”

This **flat topology** is appealing but has sharp edges.

### 1.1 Why flat Orchestrator + All Data Agents as Tools is tempting

* **Simple mental model**:
  One agent, one prompt, one place to debug.
* **Minimal wiring**:
  Just keep adding tools to the orchestrator’s `tools` list.
* **Fast for small scope**:
  For 2–3 domains and a handful of workflows, it “just works”.

### 1.2 Where this breaks down as complexity grows

As you add more domains and journeys, several problems emerge:

1. **Prompt Bloat & Cognitive Overload**

   * The orchestrator prompt must explain:

     * Banking schemas, Credit schemas, MF logic, Fraud rules, Movement rules, Policies, etc.
   * The LLM’s reasoning quality degrades as the prompt becomes a “phone book of everything”.

2. **Persona Confusion**

   * The orchestrator is now:

     * A PFM coach, a dispute specialist, a risk officer, a portfolio advisor…
   * It becomes hard to keep a **clear UX persona** and domain-appropriate tone.

3. **Lack of Domain Encapsulation**

   * If orchestrator talks directly to every tool:

     * Masking, limits, and compliance checks must be duplicated in prompt + code.
     * Any change in a domain’s rules requires editing the orchestrator prompt and logic.

4. **Poor Team & Domain Boundaries**

   * Banking team, Cards team, Investments team cannot own their domain logic cleanly.
   * Everyone modifies the orchestrator, increasing coupling and risk.

5. **Testing & Observability Pain**

   * Hard to test domain logic in isolation.
   * Traces become a single long “orchestrator did everything” story.
   * It’s harder to see *which domain logic contributed what*.

6. **Multi-turn Specialist Journeys Don’t Fit Well**

   * Long-running conversations (e.g., complex MF planning, detailed disputes) are awkward:

     * Orchestrator has to “pretend” to be a specialist for 10–20 turns.
     * Instructions for these flows bloat the main prompt further.

**Conclusion:** A flat design is fine for small demos, but for a serious multi-domain system, we need **layers**.

---

## 2. From Flat to Layered: The Architectural Trajectory

We want a progression that looks like this:

1. **Stage 1 – Single UX Agent + Tools**

   * One agent, direct tools. Good for early prototypes.

2. **Stage 2 – UX Agent + Data/Worker Agents as Tools**

   * Domain logic encapsulated in Data/Worker agents.
   * UX agent stays focused on conversation, not tools.

3. **Stage 3 – Orchestrator + Multiple UX Agents + Data/Worker Agents**

   * Orchestrator as the brain.
   * UX agents for domain-specific journeys.
   * Data/Worker agents behind UX agents and orchestrator.

4. **Stage 4 – Multi-agent Topology + A2A + Policy Agents**

   * Remote agents, cross-team boundaries, dedicated policy/fraud agents.
   * Peer-to-peer or hybrid patterns where needed.

The rest of this document defines the building blocks and shows how they fit together.

---

## 3. Google Cloud Multi-Agent Patterns

According to official Google Cloud guidance, multi-agent systems typically use a **Coordinator** or **Orchestrator** to manage specialized agents:

* **Multi-agent Coordinator Pattern**
  Dynamic routing from a coordinator to specialized sub-agents for structured tasks.

* **Hierarchical Task Decomposition**
  A “planner” agent decomposes an ambiguous goal into sub-tasks and delegates them.

* **Custom Logic Pattern**
  A coordinator uses explicit, code-level orchestration (parallel, branches, conditional routing) over multiple downstream agents.

* **Peer-to-Peer (P2P) Pattern**
  Agents communicate directly (via a bus/protocol) to collaborate on a task without a single central coordinator (swarm-like patterns).

These patterns are neutral about how you **implement** agents; ADK provides the concrete mechanisms.

---

## 4. ADK Implementation Mechanisms

In ADK, these patterns are implemented via three main mechanisms:

1. **Agent as Tool (`AgentTool`)**

   * One agent calls another agent as a **tool**: input → result.
   * Caller retains persona and continues talking to the user.

2. **Sub-agent (Agent Transfer / LLM-driven delegation)**

   * One agent **transfers** the conversation to another agent.
   * The callee becomes the active persona and handles follow-ups until another transfer.

3. **Agent-to-Agent (A2A) / Remote Agents**

   * Agents communicate over an **inter-agent protocol** (A2A) rather than in-process.
   * Used when agents live in different runtimes, teams, or platforms.

All of these operate over a shared **session** in a multi-agent app; local agents (AgentTool + Sub-agent) share `session.state`. Remote A2A agents need explicit context passing.

---

## 5. UX Agents vs Data/Worker Agents (Core Definitions)

Before choosing how agents call each other, decide **what kind of agent** you are designing.

### 5.1 UX Agents (User-Facing Agents)

* Own a **persona**, tone, and conversational UX.
* Talk directly to the end-user.
* Clarify ambiguous intent and scope.
* Format responses (Markdown, empathy, explanations).
* Example: **FinText Orchestrator**, **Money Agent**, **Banking UX Agent**.

### 5.2 Data/Worker Agents (Internal Agents)

* Internal **domain brains/services**.
* **Never** talk directly to the end-user.
* Receive **structured input** (schemas, flags, clear scopes).
* Execute tools/APIs, apply domain logic, and return **structured results** or summaries.
* If input is insufficient, they return a **“needs clarification” signal** to the caller, not a user-facing question.
* Example: **BankingDataAgent**, **CreditDataAgent**, **FraudAgent**, **MoneyMovementAgent**.

**Design rule:**

> UX agents handle **intent disambiguation + user conversation**.
> Data/Worker agents handle **domain logic + tools**, typically via **AgentTool**.

This split is what avoids “scope clarification loops” when one agent calls another.

---

## 6. Flat vs Layered Topologies

### 6.1 Flat Orchestrator with All Data Agents as Tools

**Idea:** Orchestrator has `BankingDataAgent`, `CreditDataAgent`, `MutualFundAgent`, `FraudAgent`, `MoneyMovementAgent`, etc. all as tools.

**Pros:**

* Simple to wire initially.
* One place to route and answer.
* Good for **small** systems with a handful of domains.

**Cons (as complexity grows):**

* **Prompt bloat**: All domain instructions live in one place.
* **Persona overload**: One agent tries to be “expert in everything”.
* **Domain logic leakage**: Orchestrator begins to encode domain-specific rules that belong in domain agents.
* **Hard team boundaries**: Every team must touch the orchestrator to evolve their domain.
* **Hard to test and reuse**: You can’t easily reuse Banking logic in another UX agent without duplicating it.

### 6.2 Layered Pattern: Orchestrator → UX Agents → Data/Worker Agents

A better pattern for complex systems:

* **Orchestrator UX Agent**

  * Primary entry point, global policies, cross-domain reasoning.

* **Domain UX Agents**

  * Banking UX, Credit UX, MF UX for long specialist journeys.

* **Cross-domain UX Agent**

  * Money Agent for holistic PFM across domains.

* **Data/Worker Agents**

  * BankingDataAgent, CreditDataAgent, FraudAgent, MoneyMovementAgent, etc.

**Why this layering helps:**

1. **Separation of Concerns**

   * UX vs domain logic vs tool wiring are clearly separated.
   * Different prompts for different concerns.

2. **Scalability of Reasoning**

   * Orchestrator focuses on triage + broad reasoning.
   * Domain UX focuses on narrow specialist interactions.
   * Data agents focus on correct tool usage and domain rules.

3. **Team Autonomy & Governance**

   * Domain teams own their Data/Worker agents and UX agents.
   * Orchestrator and Money Agent treat them as **APIs**, not internal schemas.

4. **Reusability**

   * BankingDataAgent can be used by:

     * Money Agent (PFM),
     * Banking UX Agent,
     * And future orchestration flows, without duplicating logic.

5. **Safety & Policy Enforcement**

   * Safety-critical flows can be centralized:

     * Policy/fraud checks can live in a **Policy Agent** or in the Orchestrator + MoneyMovementAgent.
   * Less risk of bypassing policies by directly calling low-level tools.

---

## 7. Decision Matrix: Agent as Tool vs Sub-agent

### 7.1 Use **Agent as Tool** when…

* **Pattern**: Coordinator-centric workflows (Sequential, Parallel, Custom Logic).
* **Persona**: One agent (the “brain” / UX agent) must remain the primary persona for the user.
* **Orchestration**: You need multi-step orchestration across multiple skills (e.g., check fraud → compute limits → move money).
* **State**: You want shared state automatically.

  * `AgentTool` runs in the **same session**; any state written by the tool agent is visible to the parent agent.
* **Agent Type**:

  * The callee is usually a **Data/Worker agent** (not user-facing).
* **Example**:

  * **Money Agent (UX)** calls `BankingDataAgent` and `CreditDataAgent` as tools to gather spends data and then answers the user in one unified response.

### 7.2 Use **Sub-agent (Agent Transfer)** when…

* **Pattern**: Router or hierarchical patterns with full handover.
* **Persona**: You want the user to “step into” a specialist UX (e.g., a Mutual Fund Specialist).
* **Interaction**: The specialist needs a **multi-turn** conversation with the user (e.g., collecting risk tolerance, goals, constraints over many turns).
* **Agent Type**:

  * The callee is a **UX agent** with its own persona and long-form flows.
* **Example**:

  * **FinText Orchestrator** transfers the user to a `MutualFundUXAgent` for a detailed planning session; MF UX owns the conversation until it explicitly hands back.

**Why not Agent as Tool for long deep dives?**

* **Cognitive complexity**:
  Parent UX agent would need instructions to handle every possible intermediate response from a deeply conversational tool → prompt bloat, worse reasoning.
* **Persona dilution**:
  Parent would have to “pretend” to be a specialist, losing clarity and focus.
* **State management**:
  Parent would be forced to manually manage the specialist’s long-running state, which belongs more naturally in the specialist UX agent.

### 7.3 Summary Table

| Feature                 | Agent as Tool                              | Sub-agent (Transfer)                         |
| ----------------------- | ------------------------------------------ | -------------------------------------------- |
| **ADK Mechanism**       | `AgentTool(agent=...)`                     | Listed in `sub_agents` + `transfer_to_agent` |
| **Caller Persona**      | Caller stays the persona                   | Callee becomes persona                       |
| **Typical Callee Type** | Data/Worker agent                          | UX agent (specialist)                        |
| **State**               | Shared session state                       | Shared session state                         |
| **Best For**            | Discrete calls, orchestration, aggregation | Multi-turn specialist journeys               |
| **User-facing?**        | Only caller talks to user                  | Sub-agent talks directly to user             |

---

## 8. Inter-Agent Interactions: Nervous System Analogy

Use the nervous system analogy to reason about **who should talk to whom**.

### 8.1 The Brain – Orchestrator / Main UX Agent

The **Orchestrator** (or a main UX agent) is the brain.

**Responsibilities:**

* **Triage & Routing**:
  First touchpoint for user queries; decides which domains/agents to involve.
* **Global Policy & Safety**:
  Enforces cross-domain policies (e.g., “fraud check before any money movement”, “never show raw internal IDs”).
* **Synthesis**:
  Combines outputs from multiple Data/Worker agents (Banking + Credit + Investments) into a single coherent answer.
* **Persona**:
  Primary conversational identity for broad queries.

### 8.2 The Organs – Domain Agents

* **UX Domain Agents** (Banking UX, Credit UX, MF UX): distinct personas for deep domain journeys.
* **Data/Worker Domain Agents** (BankingDataAgent, CreditDataAgent, FraudAgent, MoneyMovementAgent): encapsulate domain logic and tools.

They **should not** tightly depend on each other directly; dependencies are orchestrated via the brain or a policy layer.

### 8.3 The Spinal Cord – Reflex & Local Coupling

For **deterministic, mandatory dependencies** (reflex arcs), use **Agent as Tool** between domain agents, or between a policy layer and domain agents:

* **Example**:
  `MoneyMovementAgent` calls `FraudAgent` as a tool internally before executing any transfer.
* **Principles**:

  * Use when dependency is **fixed and policy-mandatory** (“always fraud before move”).
  * Still avoid persona shifts; this is usually Data/Worker → Data/Worker.
  * Complex reasoning or user-facing pivots should still go via the brain (orchestrator).

---

## 9. Best Practices

* **Start Simple**
  Begin with a single UX agent + a few tools. Then introduce Data/Worker agents. Only add multi-agent orchestration when the problem demands it.

* **Separate UX vs Data/Worker Agents**
  UX agents:

  * See raw user queries,
  * Clarify intent and scope,
  * Format and explain.
    Data/Worker agents:
  * Never ask the user questions,
  * Operate on structured input,
  * Return structured responses (or domain summaries).

* **Safety First**
  Encode safety-critical flows (fraud checks, limits, compliance) in:

  * The **Orchestrator** (UX + policy), or
  * A dedicated **policy agent/layer** that all risky operations must pass through.
    Do *not* scatter such invariants ad hoc inside every domain agent.

* **Leverage Shared State**
  For local agents (within one ADK app) use `session.state` to share:

  * Time windows,
  * User profile,
  * Derived metrics,
  * Flags (e.g., `temp:needs_cross_domain_view`).

* **Prefer Agent-as-Tool Across Domains**
  Particularly when:

  * Teams are separate,
  * Domains are distinct (Banking vs Credit vs MF),
  * You want a canonical domain API (BankingDataAgent) instead of everyone hitting tools directly.

---

## 10. Case Study: FinCorp Financial Ecosystem

### 10.1 Agent Roles

* **FinText Orchestrator (Main UX / Brain)**

  * Primary user-facing entry point.
  * Handles general financial questions and global policy.

* **Money Agent (PFM UX Agent)**

  * Specialized UX agent focused on **holistic financial health**:

    * “Total spends”,
    * “Can I afford X?”,
    * “Cash flow view”.

* **Banking UX Agent, Credit UX Agent, MF UX Agent**

  * Domain-specific UX agents used when you want **deep domain journeys** (disputes, card benefits exploration, MF planning).

* **Data/Worker Agents**

  * `BankingDataAgent`: Aggregates balances, spends, summaries for **FinCorp Bank** accounts.
  * `CreditDataAgent`: Card spends, dues, EMI schedules.
  * `FraudAgent`: Transaction-level risk checks.
  * `MoneyMovementAgent`: Executes transfers (subject to policy/fraud checks).

### 10.2 Holistic View (Coordinator + AgentTools)

**Goal**: “What are my total spends across banking + credit in the last 90 days?”

**Flow:**

1. User asks FinText Orchestrator.
2. Orchestrator routes to **Money Agent (UX)**.
3. Money Agent:

   * Clarifies time window or scope if needed (user-facing).
   * Writes `session.state["time_window"] = "last_90_days"`.
   * Calls:

     * `BankingDataAgent` as a tool,
     * `CreditDataAgent` as a tool.
4. Each DataAgent:

   * Uses banking/card tools (`get_transaction_summary`, etc.),
   * Returns structured spends data (e.g. JSON).
5. Money Agent:

   * Reads outputs from shared state or tool return,
   * Computes totals / trends,
   * Answers the user in one holistic response.

**Why AgentTools here?**

* Money Agent must **synthesize cross-domain** data.
* Banking/Credit agents are **workers**, not personas.
* UX + policy remains centralized.

### 10.3 Deep Dive (Sub-agents)

**Goal**: Resolve a specific disputed debit on a FinCorp Bank account.

**Flow:**

1. User says: “This ₹12,000 debit on 3rd Jan looks wrong.”
2. FinText Orchestrator routes to **Banking UX Agent** as a **sub-agent**.
3. Banking UX Agent:

   * Takes over persona.
   * Runs a multi-turn conversation:

     * Confirm account, time window, merchant, etc.
     * Calls `BankingDataAgent` repeatedly as tool for details.
4. Once dispute workflow is complete, Banking UX can:

   * Summarize outcome,
   * Optionally `transfer_to_agent("FinTextOrchestrator")` if the user asks a broad question again.

**Why Sub-agent here?**

* User is in a **multi-turn banking-specific journey**.
* A dedicated banking persona makes sense.
* The main orchestrator doesn’t need to micro-manage every turn.

---

## 11. Tool/API Sharing vs Aggregation Agents

When multiple agents need access to the same domain, choose between **direct tool access** and **Agent-as-Tool** (aggregation agents).

### 11.1 Direct Tool/API Access

**Description**: An agent calls domain tools (functions/APIs) directly.

* **Pros**:

  * Low latency.
  * Simple, fewer hops.
  * Returns native objects.

* **Cons**:

  * Tight coupling to data schema and tool details.
  * Duplicated logic (masking, limits, aggregations).
  * Higher maintenance burden when APIs change.

### 11.2 Agent-as-Tool (Domain Aggregation Agent)

**Description**: Agents call a domain **Data/Worker agent** (e.g. `BankingDataAgent`) instead of raw tools.

* **Pros**:

  * High decoupling and encapsulation.
  * One place for masking, compliance, and domain rules.
  * Team autonomy and versioning of the domain service.
  * Reusable across many UX agents / orchestrators.

* **Cons**:

  * Extra LLM/tool layer → higher latency and token usage.
  * Requires structured IO and some serialization overhead.

### 11.3 Decision Matrix

| Factor                  | Direct Tool/API Access | Agent-as-Tool (Aggregation Agent) |
| ----------------------- | ---------------------- | --------------------------------- |
| **Domain Boundary**     | Same domain            | Cross-domain / shared domain      |
| **Team Structure**      | Same team              | Different teams / services        |
| **Complexity**          | Low–Medium             | Medium–High                       |
| **Security/Compliance** | In each caller         | Centralized in domain agent       |
| **Performance**         | Best                   | Good, but extra hop               |
| **Maintenance**         | Higher long-term       | Lower for consumers               |

**Guideline**:
Use **Direct Tool Access** within a small, cohesive domain owned by one team.
Use **Agent-as-Tool with Data/Worker agents** when multiple UX agents or orchestrators need consistent, policy-compliant access to a shared domain.

---

## 12. Prompting Techniques for Sub-Agents and Worker Agents

### 12.1 Domain Context for UX Agents

For **UX agents** (Banking UX, Credit UX, MF UX), clearly define:

* Overall platform context (FinCorp and its verticals).
* The agent’s **specific domain scope** (e.g., FinCorp Bank accounts only).
* Awareness of other domains so they know when to transfer back to orchestrator instead of guessing.

**Example (UX agent):**

```text
**Domain Context**:
  * FinCorp provides Banking, Credit Card, Credit Score, Mutual Funds, and Stocks.
  * FinCorp Bank is the banking entity.
  * Your scope is strictly limited to FinCorp Bank accounts: balances, account info, and transaction history.

**Out-of-Scope Handling**:
  * If the user’s query clearly concerns another domain (e.g., credit card spends, stock trades),
    transfer to `fintext_orchestrator` instead of answering.
```

### 12.2 Mode / Caller for Dual-Use Agents (if you don’t split them)

If you keep a single agent that is sometimes UX and sometimes worker, encode an explicit **mode**:

```text
* Mode:
  * You may be called in two modes:
    * User-facing mode (`caller = "user"`): you may ask the user for clarification.
    * Internal mode (`caller != "user"`): you are being called by another agent as a tool.
      - Do NOT speak to the end-user.
      - Do NOT ask questions.
      - If inputs are insufficient, return a structured error for the caller to handle.
```

Money Agent should always call such an agent with `caller="money_agent"` (or similar) so it behaves as a worker.

### 12.3 Data/Worker Agent Prompt Pattern

For **pure Data/Worker agents** (recommended), prompts should be strictly internal:

```text
Role:
  * You are the FinCorp Banking Data Agent.
  * You never talk directly to the end-user.
  * You are called only by other agents (Money Agent, Banking UX Agent, etc.).

Behavior:
  * You receive structured input describing:
    - metric (total_spends, monthly_spend, category_breakdown, etc.),
    - time window,
    - account scope.
  * Do NOT ask clarification questions.
  * If required parameters are missing or inconsistent:
    - return {"status": "NEEDS_CLARIFICATION", "missing_fields": [...]}
      for the caller to handle.
  * Use tools like `get_account_balance`, `get_transaction_summary`, etc.
  * Return:
    - structured JSON with metrics, AND/OR
    - a concise “internal summary” the caller can format for the user.
```

This ensures that when Money Agent or a UX agent calls BankingDataAgent, it **never** prompts the user or loops on scope clarification.

## 13. Proposal: Planner + Executor Based Multi-Agent Orchestration (Experimental)

> **Status:** Proposal / Idea – **not implemented or tested yet**.  
> This section outlines a possible future direction for orchestrating multi-agent flows using a dedicated Planner + Executor pattern in ADK.

### 13.1 Motivation

Right now, multi-agent flows are primarily encoded **inside prompts**:

* The Orchestrator / UX agent is instructed to:
  * Decide which sub-agent to call,
  * Possibly call multiple sub-agents in sequence,
  * Synthesize the final answer.

In practice, this has limits:

* Once control is transferred to a sub-agent, it can be hard to **reliably come back** to the orchestrator and then move on to another agent.
* Multi-step flows (e.g., Banking → Credit Card → Money → Advisor) get baked into **one big prompt**, which:
  * Is harder to debug,
  * Is harder to reuse across journeys,
  * Can get stuck if any single sub-agent takes the conversation in an unexpected direction.

A **Planner + Executor** pattern aims to separate:

1. **Planning** – deciding *which agents* should be called, in *what sequence*, with *which dependencies*.
2. **Execution** – a deterministic loop (usually in Python) that:
   * Calls each agent step-by-step according to the plan,
   * Handles dependencies, partial failures, and aggregation.

---

### 13.2 High-Level Idea

We introduce two new logical roles:

1. **Planner Agent (LLM)**
   * Receives:
     * The user’s high-level goal and context,
     * A description of available agents (Banking, Credit Card, Money, etc.).
   * Outputs:
     * A **structured plan** describing which agents to call, in what order, and how their outputs depend on each other.

2. **Plan Executor (Code / Lightweight Agent)**
   * Receives:
     * The plan produced by the Planner,
     * The current session context (user_id, time windows, etc.).
   * Executes:
     * Each step by calling the indicated agent,
     * Collects outputs keyed by `step_id`,
     * Passes dependent outputs into later steps,
     * Produces an **execution trace** and a final aggregated result for the UX / Orchestrator agent.

This shifts orchestration from “hidden in prompts” to a **visible, debuggable plan + execution loop**.

---

### 13.3 Proposed Plan Schema (Draft)

A possible minimal JSON schema for the Planner’s output:

```json
{
  "plan": [
    {
      "step_id": "1",
      "agent_name": "banking_agent",
      "purpose": "Fetch last 90 days FinCorp Bank transaction summary.",
      "inputs": {
        "time_window_days": 90
      },
      "depends_on": []
    },
    {
      "step_id": "2",
      "agent_name": "credit_card_agent",
      "purpose": "Fetch last 90 days credit card transaction summary.",
      "inputs": {
        "time_window_days": 90
      },
      "depends_on": []
    },
    {
      "step_id": "3",
      "agent_name": "money_agent",
      "purpose": "Combine bank + card summaries into holistic cashflow view.",
      "inputs": {
        "use_results_of": ["1", "2"]
      },
      "depends_on": ["1", "2"]
    }
  ]
}

---
