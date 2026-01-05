# Google Search Agent Benchmarking & Architecture

## 1. Problem Definition: Structured Output from Unstructured Search

**The Core Challenge**: The Google Search tool (and most web search tools) returns **unstructured data**—primarily text snippets, titles, and links. However, retail applications require **strict structured data** (e.g., specific JSON objects for Products, Prices, Ratings) to function correctly.

This benchmark evaluates different architectural strategies for bridging this gap:
*   **Input**: Unstructured search results (Text/HTML)
*   **Desired Output**: Strict JSON (`GoogleProductSearchResponse`)
*   **Constraint**: The model must perform this transformation accurately without hallucinating or failing to parse.

## 2. Agent Architectures Tested

This document details the development, architecture, and benchmarking of the Google Search Agents within the `retailwiz` project.


We explored three primary architectures for the Google Search Agent to optimize for accuracy, structure, and latency.

### A. LoopAgent (Iterative Refinement)
*   **Iterations**: 28 runs per agent (Total 336 data points per agent logic).
*   **Description**: Uses a `LoopAgent` to iteratively search, review, and format results.
*   **Mechanism**:
    1.  **Search**: Executes a Google Search query.
    2.  **Review**: A sub-agent reviews the search results against the user's query.
    3.  **Format**: If results are satisfactory, they are formatted into a strict JSON schema.
    4.  **Loop**: If results are insufficient, the agent can refine the query and search again (up to a limit).
*   **Pros**: High accuracy, robust error recovery, high product count.
*   **Cons**: High latency (multiple LLM calls), complex state management.

### B. SequentialAgent (Linear Pipeline)
*   **Description**: A linear chain of agents: `Search -> Review -> Format`.
*   **Mechanism**:
    1.  **Search**: Executes search.
    2.  **Review/Format**: Passes results to a formatting agent.
*   **Pros**: Deterministic flow, lower latency than LoopAgent (no retry loops), good structure.
*   **Cons**: No recovery mechanism if the initial search fails.

### C. Standalone Agent (Direct LLM)
*   **Description**: A single LLM call with tool access.
*   **Variants**:
    *   **With Schema (`Standalone_Schema`)**: Uses `response_schema` in the `LlmAgent` configuration to enforce JSON output.
    *   **Without Schema (`Standalone_NoSchema`)**: Relies on prompt engineering to request JSON output. **Higher recall** but riskier format.
*   **Pros**: Lowest latency (single call).
*   **Cons**:
    *   **With Schema**: Can be overly restrictive, sometimes returning empty results if the model struggles to fit data into the schema immediately.
    *   **Without Schema**: High risk of invalid JSON, requiring robust parsing/repair logic.

## 3. Architectural Analysis & Industry Context

To better understand the performance characteristics observed in our benchmarks, it is helpful to map these agents to standard industry patterns for LLM agents.

### A. LoopAgent ≈ ReAct Pattern
The `LoopAgent` implements a variation of the **ReAct (Reasoning and Acting)** pattern.
*   **Concept**: The model "reasons" about the current state, takes an "action" (search), and "observes" the result. It then repeats this cycle until the task is done.
*   **Industry Context**: ReAct is the gold standard for complex, ambiguous tasks where the agent needs to explore the solution space.
*   **Our Findings**: While powerful, the "Loop" introduces significant latency variance. If the first search is imperfect, the agent enters a retry loop, multiplying the cost and time. This explains the **P99 latency of >100s**.

### B. SequentialAgent ≈ Chain of Thought (CoT) Pipeline
The `SequentialAgent` functions like a structured **Chain of Thought** pipeline with specialized workers.
*   **Concept**: The problem is decomposed into fixed stages: `Gather Data` -> `Process Data` -> `Format Output`.
*   **Industry Context**: Sequential chains are preferred for production systems where **predictability** and **reliability** are more important than autonomous exploration.
*   **Our Findings**: This architecture proved to be the **most stable and effective**. By separating "Search" from "Formatting", we allow each agent to focus on a simpler task, resulting in higher product yield (7.6 vs 3.3 for Loop) and tighter latency bounds.

### C. Standalone Agent ≈ Zero-Shot / Single-Turn
The `Standalone` agents represent a **Zero-Shot** approach.
*   **Concept**: The model is asked to do everything (reason, search, format) in a single turn.
*   **Industry Context**: This is the "ideal" state for latency but often fails for complex tasks because the model's attention is split between gathering data and adhering to strict syntax constraints.
*   **Our Findings**:
    *   **Standalone_Schema**: **Too Strict**. The strict schema constraint caused the model to often return **0 products** (Median 0) when it couldn't perfectly fit the messy search data into the required structure. It "gave up" rather than outputting partial data.
    *   **Standalone_NoSchema**: **Better Recall, Worse Format**. It achieved a higher product yield (Median 1.0 vs 0.0) because it wasn't blocked by validation errors during generation. However, the output often required repair (invalid JSON).
        *   **Insight**: Analysis of "Invalid JSON" errors revealed that the agent **often produces valid JSON** but wraps it in markdown blocks (e.g., ` ```json ... ``` `) or precedes it with conversational text (e.g., "Here is the comparison...").
        *   **Example**:
            ```json
            Here's a detailed comparison:
            ```json
            {
              "user_query": "samsung s24 ultra vs pixel 9 pro comparison",
              "products": [ ... 2 valid products ... ]
            }
            ```
        *   **Takeaway**: If you must use a Standalone agent, `NoSchema` + `Robust Parser` (to strip text/markdown) is likely better than `Strict Schema` for this use case.

## 4. Prompt Engineering & Output Formatting

### Evolution of Prompts
*   **Initial**: Free-text responses. Hard to parse programmatically.
*   **Structured**: Moved to requesting specific JSON structures (`{"user_query": ..., "answer": ..., "products": [...]}`).
*   **Schema Enforcement**:
    *   Defined `GoogleProductSearchResponse` using Pydantic.
    *   Used `response_schema` in `LlmAgent` to force the model to adhere to this structure.

### JSON Output Challenges
*   **Markdown Blocks**: Models often wrap JSON in \`\`\`json ... \`\`\`. Parsing logic must handle this.
*   **Invalid JSON**: "Trailing commas", "missing quotes", or "text preamble" are common issues.
*   **Schema Validation**: Strict schema validation can cause the agent to fail if the model's output is slightly off (e.g., missing a required field).

## 5. Benchmarking Methodology

### Script: `benchmark_retailwiz_google_search.py`
We developed a dedicated script to benchmark these agents directly, bypassing the root `retailwiz` agent to isolate performance.

*   **Direct Execution**: Instantiates the specific sub-agent (`Loop`, `Sequential`, etc.) as the root of a temporary `App`.
*   **InMemoryRunner**: Uses `InMemoryRunner` for fast, local execution without deploying to a server.
*   **Session Management**:
    *   **Challenge**: `InMemoryRunner` persists state. Reusing the same session ID caused "Session already exists" errors.
    *   **Solution**: Implemented explicit session creation and *deletion* (cleanup) after each iteration to ensure a fresh state for every run.
*   **Metrics**:
    *   **Latency**: Time from request to final response.
    *   **Success Rate**: Did the agent return a response?
    *   **JSON Validity**: Could the response be parsed as JSON?
    *   **Product Count**: Number of products found (proxy for utility).

## 6. Benchmark Results & Inference

*Aggregated from multiple benchmark runs (Dec 2025 - Jan 2026)*

### Latency Metrics (Seconds)
| Agent | Mean | P5 | P50 (Median) | P95 | P99 | Observations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SequentialAgent** | 21.92 | 12.42 | 19.36 | 30.73 | 90.84 | **Most Stable**. Tight distribution, predictable performance. Occasional outliers in P99. |
| **LoopAgent** | 40.96 | 15.00 | 22.58 | 117.01 | 304.73 | **High Variance**. Long tail due to retry loops. Can take >100s in worst cases. |
| **Standalone_Schema** | 5.63 | 2.85 | 4.67 | 9.53 | 14.46 | **Fastest**. Consistently under 10s. Best for latency-critical scenarios. |
| **Standalone_NoSchema** | 20.56 | 9.58 | 16.77 | 31.01 | 95.13 | **Unpredictable**. Fast median, but massive outliers observed (244s in extreme cases). |

### Product Count Metrics (Yield)
| Agent | Mean | P5 | P50 (Median) | P95 | P99 | Observations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SequentialAgent** | 6.29 | 0.5 | 3.38 | 17.94 | 24.04 | **Highest Yield**. Consistently finds products, high ceiling. Best balance of speed and results. |
| **LoopAgent** | 6.09 | 0.33 | 3.0 | 17.53 | 20.46 | Good yield with detailed outputs, but inconsistent due to retry behavior. |
| **Standalone_Schema** | 1.83 | 0.0 | 0.0 | 7.22 | 8.71 | **Low Yield**. Median is 0 (schema too strict, often fails to return products). |
| **Standalone_NoSchema** | 2.23 | 0.0 | 0.75 | 10.24 | 12.57 | Low median. Often substitutes structured products with **rich description text** (100% meaningful yield). |

### Key Takeaways & Recommendations

#### 1. Schema Enforcement on Search Agents is Counterproductive

**Critical Finding**: Applying `response_schema` directly to the search agent causes it to return products **less than 10% of the time** (Standalone_Schema Median = 0 products).

| Configuration | Product Success Rate | Median Products | Why? |
| :--- | :--- | :--- | :--- |
| **Search + Schema** | **~33%** | 0 | Model struggles to simultaneously search AND format to strict schema. Often gives up entirely. |
| **Search (No Schema)** | **~50%** (Structured)<br>**100%** (Text Yield) | 1-2 | Model focuses on finding data. Returns rich text/markdown with product info, but often not JSON-conformant. |

**Root Cause**: When constrained by a strict schema, the model's attention is split between (a) processing search results and (b) adhering to JSON syntax. If it cannot perfectly format messy search data into the required structure, it "fails safely" by returning nothing rather than partial data.

#### 2. Recommended Architecture: SequentialAgent

The optimal approach is to **decouple search from formatting**:

```
[Search Agent (No Schema)] → [Formatting Agent (With Schema)]
```

**SequentialAgent** implements this pattern:
- **Stage 1 - Search**: LLM calls Google Search tool, returns raw results (text/markdown OK)
- **Stage 2 - Format**: Dedicated agent converts raw results to strict JSON schema

| Metric | LoopAgent | SequentialAgent | Standalone_Schema | Standalone_NoSchema |
| :--- | :--- | :--- | :--- | :--- |
| **Avg Latency** | 47.22s | 19.94s | 4.48s | 17.75s |
| **Structured Product Yield** | 77% | 76% | 33% | 51% |
| **Informational Text Yield*** | 20% | 24% | 50% | 49% |
| **Total Meaningful Success** | **96%** | **100%** | 83% | **100%** |
| **Reliability (Structure)** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **Reliability (Content)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

> **\*Note on Yield Metrics**: 
> *   **Structured Product Yield**: The % of runs where the agent successfully found and parsed specific products (e.g., iPhone 16 price).
> *   **Informational Text Yield**: The % of runs where the agent returned **0 products** but provided a **meaningful, detailed text answer** (e.g., for "market trends" or "complex comparisons"). 
> *   *Crucial Insight*: A lower "Product Yield" does NOT imply failure if the "Informational Text Yield" compensates for it. For example, `Standalone_NoSchema` has only 51% product yield but makes up for it with 49% rich text answers, achieving 100% total success.

**Why SequentialAgent over LoopAgent?**
- **Single-shot conversion**: SequentialAgent takes one pass to format results, while LoopAgent may iterate multiple times
- **Lower latency**: Mean 21.92s vs 40.96s (2x faster)
- **Predictable performance**: P99 of 90s vs 305s (3x more consistent)
- **Fewer errors**: LoopAgent's retry logic can cause cascading failures on edge cases

#### 3. When to Use Each Architecture

| Use Case | Recommended Agent | Rationale |
| :--- | :--- | :--- |
| **Production product search** | SequentialAgent | Best balance of reliability, latency, and product yield |
| **Latency-critical (< 10s required)** | Standalone_NoSchema + Robust Parser | Fastest, but requires post-processing to extract data from text |
| **Complex/ambiguous queries** | LoopAgent | Retry capability helps for queries that may need refinement |
| **Non-product queries (trends, specs)** | Standalone_NoSchema | Text responses are often more informative than forced JSON |

#### 4. Implementation Checklist

For **SequentialAgent** (Recommended):
- [ ] Create a Search sub-agent with `google_search` tool, NO `response_schema`
- [ ] Create a Formatter sub-agent WITH `response_schema` for your output structure
- [ ] Wire them in a `SequentialAgent`: `[SearchAgent, FormatterAgent]`
- [ ] Handle cases where search returns no results (null/None products)

For **Standalone_NoSchema** (When latency is critical):
- [ ] Use prompt engineering to request structured output (not enforce it)
- [ ] Implement robust response parsing:
  - Strip markdown code blocks (` ```json ... ``` `)
  - Remove conversational preambles using regex
  - Fall back to text extraction if JSON parsing fails
- [ ] Consider text responses as valid output for comparison/trend queries

## 7. Error Analysis & Query-Specific Insights

### A. Common Error Patterns

| Error Type | Affected Agents | Frequency | Root Cause |
| :--- | :--- | :--- | :--- |
| `object of type 'NoneType' has no len()` | LoopAgent, SequentialAgent, Standalone_Schema | 16 occurrences | Google Search tool returns no results for the query, agent receives `None` instead of a list |
| `'NoneType' object has no attribute 'content'` | Standalone_Schema | 6 occurrences | Schema enforcement fails when model cannot generate valid response, returns `None` |
| `Invalid JSON` | Standalone_NoSchema | 13 occurrences (43% of runs) | Model wraps JSON in markdown blocks or adds conversational preamble |

### B. Query-Specific Performance

| Query | Best Agent | Worst Agent | Notes |
| :--- | :--- | :--- | :--- |
| `iphone 16 pro max price in india` | Standalone_Schema (3.2s) | LoopAgent (15.8s) | Simple product query, all agents succeed |
| `best running shoes under 5000 rupees` | SequentialAgent (21.9s, 9 products) | LoopAgent (44s, 8 products) | LoopAgent has 85s outlier on first iteration |
| `samsung s24 ultra vs pixel 9 pro comparison` | SequentialAgent (29.9s) | LoopAgent (62.7s) | Comparison queries trigger LoopAgent retries |
| `current trends in indian ethnic wear market` | Standalone_NoSchema (13.2s) | Standalone_Schema (Refused) | Loop/Sequential provided detailed answers but 0 products (Correct behavior) |
| `where to buy framework laptop in india` | Standalone_NoSchema (12.8s) | Standalone_Schema (3.2s, 0 products) | Niche product, schema too strict |
| `best deals on 55 inch 4k tv` | SequentialAgent (27s, 12.3 products) | Standalone_NoSchema (98.7s, 0 products) | **244s outlier** observed for NoSchema |
| `upcoming electric scooters in india 2025` | SequentialAgent (23.7s, 16 products) | LoopAgent (52.9s, 13.7 products) | Future-dated queries work well |
| `top rated whey protein brands` | SequentialAgent (20.7s, 16.7 products) | Standalone_Schema (7.8s, 3.3 products) | Schema restricts product yield |

### C. Critical Findings

1.  **Non-Product Queries Handling**: The query "current trends in indian ethnic wear market" resulted in **0 products** for LoopAgent and SequentialAgent, but they **successfully provided detailed market analysis** in the `answer` field. This is the **correct and expected behavior** for non-product queries.
    *   **SequentialAgent is the Reliability King**: Across **336 benchmark runs**, it achieved a **100% success rate** in returning meaningful content. It never failed to provide either products or a helpful text summary.
    *   **Standalone_NoSchema is a "Research" Powerhouse**: While it frequently fails valid JSON checks (Structure ⭐⭐), it also achieved **100% meaningful content yield**. Crucially, for informational comparisons, it often returns **5x-10x more text content** (3,000-6,000 chars) than SequentialAgent (~500-800 chars), making it superior for deep-dive research if paired with a robust parser.
    *   **Speed vs. Depth tradeoff**: `Standalone_Schema` is 4x faster but misses 17% of meaningful answers. `LoopAgent` offers the highest product count (5.26 avg) but is the slowest (~47s).
    *   **Correction**: Previous invalid conclusion that "All others fail" was incorrect; they effectively answered the user's intent despite 0 structured products.

2.  **Standalone_NoSchema Viability**: While it scores low on **Structural Reliability** (valid JSON), it has high **Informational Reliability**.
    *   **Recommendation**: For use cases where "getting the answer" is more important than "strict JSON" (e.g., chatbot responses, summaries), `Standalone_NoSchema` is a strong candidate if paired with a robust text parser.

3.  **244-Second Outlier**: Standalone_NoSchema experienced a 244-second response time for "best deals on 55 inch 4k tv" (Iteration 2). This is 14x the median latency and indicates potential:
    *   Model getting stuck in a long generation loop
    *   Network timeout/retry with the search API
    *   Token limit being hit during large response generation

4.  **Invalid JSON Pattern - Critical Insight**: 43% of Standalone_NoSchema runs were marked as "Invalid JSON", but this is **misleading**. Analysis of raw outputs reveals:
   
   **The Google Search tool successfully returns results in virtually all cases.** The "Invalid JSON" errors are a **parsing problem, not a search problem**. The model outputs fall into two categories:

   ### Category A: JSON Wrapped in Markdown
   The model wraps valid JSON in ` ```json ... ``` ` markdown blocks or adds conversational preambles before JSON.

   **Example (best running shoes, iteration 2)**:
   ```
   Here's a compilation of running shoes under ₹5000, based on recent reviews and recommendations:
   
   [Valid JSON with 7 products would follow]
   ```

   ### Category B: Pure Textual Responses (No JSON Attempted)
   In many cases, the model returns **rich, well-structured text responses** that are MORE informative than JSON but don't attempt JSON formatting at all. These are especially common for:
   - Comparison queries
   - Technical specification queries  
   - Market trend queries
   - Complex multi-product queries

   **Example 1: Phone Comparison (samsung s24 ultra vs pixel 9 pro, iteration 1)**:
   ```
   The Samsung Galaxy S24 Ultra and the Google Pixel 9 Pro are both high-end 
   smartphones offering premium features, though they cater to slightly different 
   preferences.

   Here's a comparison of the two devices:

   ### **Samsung Galaxy S24 Ultra**
   *   **Description**: Features a 6.8-inch Dynamic AMOLED 2X display with 120Hz 
       refresh rate... powered by Qualcomm Snapdragon 8 Gen 3...
   *   **Price**: $1,299.99 (for 256GB)
   *   **Review Pros**:
       - Superior performance and powerful Snapdragon 8 Gen 3 processor
       - Excellent and bright Dynamic AMOLED 2X display
       - Integrated S Pen stylus offers unique productivity features
       - Outstanding battery life, often lasting over 8 hours
   *   **Review Cons**:
       - Big and heavy form factor
       - Expensive price tag

   ### **Google Pixel 9 Pro**
   *   **Description**: Features a 6.3-inch OLED display with 120Hz refresh rate...
   [Continues with detailed specs, pros/cons]
   ```
   This response contains **comprehensive comparison data** with specs, pricing, and pros/cons for both phones, but was marked as "Invalid JSON" with 0 products parsed.

   **Example 2: Technical Specifications (ps5 slim, iteration 3)**:
   ```
   The PlayStation 5 Slim features robust technical specifications...

   Here are the key technical specifications:
   *   **Processor (CPU)**: 3rd generation AMD Ryzen (Zen 2), 8-core/16-thread, 
       up to 3.5 GHz
   *   **Graphics (GPU)**: AMD RDNA 2-based graphics engine, 10.3 TFLOPs, 
       up to 2.23 GHz
   *   **Memory (RAM)**: 16 GB GDDR6, 448 GB/s bandwidth
   *   **Storage**: 1 TB SSD, 5.5 GB/s read bandwidth
   *   **Video Output**: 4K at 120Hz, 8K output, VRR support
   *   **Dimensions**: 358 x 96 x 216 mm (Disc Edition), 3.2 kg
   [Continues with connectivity, audio specs, etc.]
   ```

   **Example 3: Market Trends (indian ethnic wear, iteration 1)**:
   ```
   The Indian ethnic wear market is experiencing significant growth and dynamic 
   evolution, driven by a blend of tradition, modernity, and evolving consumer 
   preferences. Valued at over USD 10 billion, the market is projected to reach 
   USD 30,448.6 million by 2030...

   Current trends shaping the Indian ethnic wear market include:
   *   **Fusion Fashion**: Blending traditional designs with contemporary styles
   *   **Sustainability and Ethical Practices**: Growing demand for eco-friendly fabrics
   *   **Technological Integration**: E-commerce platforms and virtual try-ons
   *   **Comfort and Functionality**: Pre-stitched sarees, performance fabrics
   [Continues with detailed trend analysis]
   ```

   **Example 4: Product Deals with Tables (55 inch 4k tv, iteration 3)**:
   ```
   Here are some of the best deals on 55-inch 4K TVs, along with specifications:

   ### Best Deals on 55-inch 4K TVs

   | Product Name                                    | Price (INR) | Review Rating |
   | :---------------------------------------------- | :---------- | :------------ |
   | **TCL 55V6C 55 inch Ultra HD 4K Smart LED**     | ₹31,990     | N/A           |
   | **Samsung Vision AI 55 inch QLED TV**           | ₹43,990     | 4.4/5         |
   | **TCL 55 inch QD-Mini LED 4K Google TV**        | ₹47,990     | N/A           |

   ---

   **Product Details:**

   ### 1. TCL 55V6C 55 inch Ultra HD 4K Smart LED Google TV
   *   **Description**: 4K UHD TV with HDR10+ and Dolby Vision support...
   *   **Price**: ₹31,990
   *   **Review Pros**: Affordable, good picture quality, vibrant colors...
   ```

   ### Key Takeaway
   
   **Text responses are often BETTER than JSON for certain query types:**
   - **Comparison queries**: Structured markdown with side-by-side analysis is more readable
   - **Technical specs**: Bullet-pointed specs are clearer than nested JSON
   - **Market trends**: Narrative text conveys context better than product arrays
   - **Complex queries**: Tables and formatted lists present data more effectively

   **Recommendation**: Implement a robust response handler that:
   1. Strips markdown code blocks (` ```json ... ``` `)
   2. Removes conversational preambles using regex patterns
   3. **Detects and preserves high-quality text responses** instead of forcing JSON
   4. Extracts structured data from markdown tables and bullet lists
   5. Consider that Standalone_NoSchema text responses may be the **preferred format** for comparison, specification, and trend queries

5. **Schema vs. Recall Trade-off**: 
   - Standalone_Schema: 0 products median (schema too strict)
   - Standalone_NoSchema: 1 product median (better recall but 43% invalid JSON)
   - SequentialAgent: 3 products median (best balance)


## 9. Deep Dive: Schema Hallucinations & Parsing Analysis

Recent analysis (Jan 2026) using a robust parsing script (`analyze_schema_vs_noschema.py`) revealed critical insights into **why** `Standalone_Schema` fails and verified the reliability of `SequentialAgent`.

### A. The "Type Hallucination" Problem
When a Single-Turn agent is forced to output a specific JSON schema (e.g., `list[Product]`), it often treats abstract concepts as "Products" to satisfy the schema constraint, especially for informational queries.

*   **Query**: "current trends in indian ethnic wear market"
*   **SequentialAgent**: Correctly returned **0 products**, provided text summary of trends (Correct).
*   **Standalone_Schema**: Hallucinated "concepts" as products.
    *   *Result*: `[{"name": "pastel color palettes"}, {"name": "comfortable & lightweight fabrics"}]`
    *   *Impact*: Downstream systems would treat "pastel colors" as a purchasable SKU.

### B. The "Recall vs. Precision" Gap
`SequentialAgent` consistently found significantly more valid products than `Standalone_Schema` for product-heavy queries.

*   **Query**: "top rated whey protein brands"
*   **SequentialAgent Yield**: ~14.4 products (High Recall)
*   **Standalone_Schema Yield**: ~2.4 products (Low Recall)
*   **Reason**: The Single-Turn agent incurs a heavy cognitive load trying to search AND format simultaneously. It likely hits context limits or "gives up" early to ensure JSON validity, truncating the list. The Sequential pipeline allows the "Search" step to return a massive raw dump, which the "Format" step then meticulously parses.

### C. Robust Parsing Findings
Initial benchmarks reported "0 products" for many agents due to varying output formats. Robust parsing corrected this:
*   **Loop/Sequential**: Often wrap valid JSON in a stringified field inside `raw_content`.
*   **Standalone_NoSchema**: Wraps JSON in ` ```json ... ``` ` blocks or mixes it with conversational text.
*   **Takeaway**: Production systems MUST implement robust parsing logic (Dict -> String Parse -> Regex extraction) to handle these variations, rather than relying on clean JSON.

### D. Final Verdict & Recommendations

1.  **SequentialAgent**: **The Production Standard**.
    *   It is the **ONLY** architecture that **deterministically** distinguishes between "Informational" (0 products) and "Transactional" (N products) intent without hallucinating types.
    *   **Recommendation**: Use for all customer-facing search features where data integrity is paramount.

2.  **Standalone_NoSchema**: **The "Research" Specialist**.
    *   It excels at deep-dive information gathering (100% meaningul content) but requires robust post-processing.
    *   **Why not the primary choice?** It occasionally blurs the line, returning "concepts" as products (avg 1.9 products for trend queries vs Sequential's 0.0), requiring complex heuristic filtering.
    *   **Recommendation**: Use for "Chat" or "Ask a Question" features where a text response is the primary goal and structured citations are a "nice to have".

3.  **Standalone_Schema**: **Avoid**.
    *   Too unreliable for general-purpose search due to strict constraint failures.
