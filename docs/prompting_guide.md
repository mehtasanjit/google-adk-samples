# Agentic Prompt Engineering Guide
## Synthesized from FinText, Banking, & RetailWiz Architectures

This guide distills the prompting principles used across the high-reliability agents in this codebase, combined with [Google Cloud Vertex AI Prompt Design Strategies](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/prompt-design-strategies).

---

## 1. Core Philosophy: "The Authoritative Commander"

Unlike standard conversational prompts (e.g., "Please help the user"), these agents function as determining systems. The language is **imperative**, **absolute**, and **authoritative**.

### Key Phraseology
*   **"Strictly and Unmistakably"**: Used 20+ times across the codebase to enforce precision.
    *   *Note*: While Vertex AI warns against "overt manipulation" (e.g., "bad things will happen"), these phrases are used here to define **hard constraints**, not to apply emotional pressure.
*   **"Under no circumstance"**: Defines hard boundaries for security and scope.


*   **"ABSOLUTELY MANDATORY"**: Highlights non-negotiable prerequisites (like Authentication).

**Principles:**
1.  **Ambiguity is a Bug**: Do not leave room for interpretation.
2.  **Gatekeeping is Primary**: Verify *who* the user is and *what* they want before acting.
3.  **Deterministic Workflows**: Force the model to think in defined steps.

---

## 2. The Structural Blueprint

Every robust agent follows a consistent 4-part anatomy.

### Part A: Role & Persona (`Role`)
Define *who* the agent is and its specific "Specialist" nature.
> **You are the Funds Transfer Specialist.** Your persona is functional, secure, and direct.

### Part B: Domain & Scope (`Domain & Scope`)
Define *where* the agent operates and, critically, where it does **NOT**.
*   **Inclusion**: "Strictly limited to Impact Correlation on Stocks."
*   **Exclusion**: "You must NOT provide general news reporting."

### Part C: The Instruction Set (`Instructions`)
A numbered, step-by-step algorithm ("Chain of Thought") the model must follow.
*   **Step 1**: Intent Analysis (Analyze input).
*   **Step 2**: Scope Check (Validate against Part B).
*   **Step 3**: Tool Selection/Execution.

### Part D: Output & Tools (`Output Format`, `Tools`)
Explicit definitions of tools and the required JSON schema for the final response.

---

## 3. The "Safety First" Protocol

Security and correctness are engineered into the prompt logic, not just the system wrapper.

### Pattern 1: The Authentication Gate
For sensitive agents (Banking/FinText), the **FIRST** instruction is always an authentication check.
```markdown
* **Step 1: Authentication (ABSOLUTELY MANDATORY)**:
  * For *every single query*, strictly call `check_login_status`.
  * If "Not logged in", STOP processing immediately.
```

### Pattern 2: The Scope Gate
Before answering, the agent must explicitly validate the query against its allowed domain.
```markdown
* **Step 1: Intent Analysis**:
  * Determine if the intent falls *strictly* within [Allowed Domains].
  * If intent is ambiguous or out-of-scope, *politely but firmly refuse*.
```

---

## 4. Advanced Pattern: Separation of Concerns

Aligning with Vertex AI's "Break down complex tasks" strategy, these agents split cognitive load.

### Planner vs. Executor
*   **Planner Agent**: Pure reasoning. Outputs a JSON plan. Does *not* execute tools.
*   **Executor Agent**: Pure action. Takes the plan and calls tools. Does *not* replan.

### Search vs. Formatting (RetailWiz)
*   **Sequential Agent Pattern**:
    1.  **Search Agent**: returns a messy, comprehensive raw dump of information.
    2.  **Formatting Agent**: takes the raw text and maps it to a strict Pydantic Schema.
*   **Why?** Single-turn agents often hallucinate strict schemas (e.g., inventing products) to satisfy formatting constraints. Splitting the task improves reliability.

---

## 5. Vertex AI Alignment Checklist

| Vertex AI Strategy | Implemented Pattern | Example File |
| :--- | :--- | :--- |
| **Give Clear Instructions** | Numbered "Stepwise" Instructions | `fintext/planner.py` |
| **Adopt a Persona** | "You are the [X] Specialist" | `banking/subagents/funds_transfer/agent.py` |
| **Use Constraints** | "Strictly limited to...", "Refusal Policy" | `retailwiz/agent.py` |
| **Chain of Thought** | "Analyze user intent...", "Provide Reasoning" | `fintext/planner.py` (`{REASONING_TAG}`) |
| **Few-Shot Prompting** | JSON Output Examples | `fintext/planner.py` (Snippet 89-109) |

---

## 6. Template Snippet

Use this template for new agents:

```python
agent = Agent(
    name="new_specialist_agent",
    description="A specialist agent for [Domain]",
    instruction="""
      **Role:**
        * You are the **[Specialist Name]**.
        * Your goal is to **strictly** assist with [Specific Task].

      **Domain & Scope:**
        * **Allowed**: [List A, List B]
        * **Excluded**: [Everything else]

      **Instructions:**
        * **Step 1: Analyze Intent**: Determine if the query is strictly within scope.
        * **Step 2: [Action]**: [Specific instruction].
        * **Step 3: [Output]**: Format the response as [Required Format].

      **Constraints:**
        * You must **strictly and unmistakably** use [Tool Name] for [Action].
        * Under no circumstance shall you [Forbidden Action].
    """
)
```

---

## 7. Formatting & Structure: What Gemini "Likes"

The project uses a **Markdown-heavy** style, while Vertex AI documentation often suggests **XML tags**. Both are effective if consistent.

### A. The Project Standard (Markdown)
This codebase relies on **visual hierarchy** using Markdown headers and bullets.
*   **Pros**: Human-readable, native to Python docstrings.
*   **Best For**: Complex instructions with nested logic.

```markdown
**Role:**
  * You are the [X] Agent.

**Instructions:**
  * **Step 1**: ...
    * Sub-step 1a: ...
```

### B. The Vertex AI Standard (XML Tags)
Vertex AI documentation officially recommends using XML-like tags to delimiter sections, helping the model parse "blocks" of context. 
*   **Reference**: [Vertex AI Prompt Design Strategies - Sample Prompt Template](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/prompt-design-strategies#sample-prompt-template)
*   **Pros**: Extremely clear machine-parsable boundaries; prevents "delimiter collision" with user content.
*   **Best For**: Injecting large context blocks, RAG outputs, or few-shot examples.

```xml
<INSTRUCTIONS>
  1. Analyze user intent...
</INSTRUCTIONS>

<OUTPUT_FORMAT>
  JSON object with...
</OUTPUT_FORMAT>
```

### Recommendation
**Stick to the User's Markdown Standard** for consistency, but ensure **Delimiter Clarity**:
*   Use `***` or `---` to separate major sections.
*   Use **Code Blocks** (```json) for output formats to prevent the model from "leaking" JSON into text.

---

## 8. Pattern: Context Injection & Grounding

Robust agents don't just rely on training data; they are anchored in dynamic runtime context.

### A. Temporal Grounding (The "Time Anchor")
LLMs are frozen in their training time. To answer "recent" queries, you must force a "Now" anchor.
*   **The Pattern**:
    ```markdown
    * **Step 1**: You **MUST** first call the `get_current_datetime` tool to get the current date and time.
    ```
*   **Why**: Prevents temporal hallucinations (e.g., thinking "today" is 2023).

### B. Global Environmental Context
Instead of hardcoding "India" or "INR" into every agent, use **Global Instructions** injected at runtime (e.g., via `GlobalInstructionPlugin`).
*   **The Pattern**:
    ```python
    global_instructions = """
      **Global Context:**
        * **Location**: India
        * **Currency**: INR (₹)
    """
    ```
*   **Why**: Allows the same agent code to be deployed in different regions without code changes.

---

## 9. Pattern: Iterative Critique (The "Loop")

For complex tasks (like Research), a single pass often fails. The **Loop Pattern** introduces a specific "Reviewer" or "Critique" step.

*   **Mechanism**:
    1.  **Worker Agent**: Performs the task (e.g., Search).
    2.  **Reviewer Agent**: Evaluates the output against the *original user intent*.
    3.  **Feedback**: If incomplete, the Reviewer sends specific feedback back to the Worker (loops). 
    4.  **Exit**: Only calls `exit_loop` when the Reviewer is satisfied.
*   **Prompt Phraseology**:
    > "If CRITICAL information is missing - you MUST ask the Sub-Agent to find it. Be specific about what is missing."

---


---

## 10. Pattern: Explicit Reasoning Blocks (`{REASONING_TAG}`)
To improve logical consistency, force the model to "think" *before* it acts or formats output.
*   **The Pattern**:
    ```markdown
    {REASONING_TAG}
      * You must provide reasoning and rationale for why this workflow is correct and complete.
      * [Analysis] -> [Conclusion]
    
    {ACTION_TAG}
      * You must strictly execute the exact plan.
    ```
*   **Why**: Separates the "messy" cognitive work from the strict JSON/Action output, preventing "thinking" text from leaking into JSON fields.

---

## 11. Pattern: Handling "Zero Results" (The Null Hypothesis)
Hallucinations often occur when the model feels "pressured" to provide *something* when nothing exists.
*   **The Fix**: Explicitly define the "Success" AND "Failure" states.
    > "If the search yields **zero results**, you must **strictly** return an empty list `[]`. Do NOT invent products to fill the schema."
*   **Why**: Removes the implicit penalty for "finding nothing," making honesty the path of least resistance.

---

## 12. Summary Checklist for New Prompts

1.  [ ] **Authoritative Tone**: Did you use "Strictly", "Unmistakably", "Mandatory"?
2.  [ ] **Role & Scope**: Is the domain defined *negatively* (what it is NOT)?
3.  [ ] **Safety Gates**: Are Auth and Scope checks Step 1 & 2?
4.  [ ] **Grounding**: Is `get_current_datetime` required?
5.  [ ] **Structure**: Are you using the Standard 4-Part Blueprint?
6.  [ ] **Reasoning**: Did you ask for `{REASONING_TAG}` before complex JSON?

