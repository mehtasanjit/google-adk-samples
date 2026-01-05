import os
import sys
import asyncio
import csv
import time
import json
import datetime
import signal
import google.genai.types as types
from typing import List, Dict, Any
from dotenv import load_dotenv

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print("\n\n⚠️  Ctrl+C detected. Finishing current iteration and exiting...")
    shutdown_requested = True

# Script is in retailwiz/benchmark_retailwiz_google_search.py
# Root is 1 levels up: ../
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Load env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from google.adk.apps.app import App
from google.adk.runners import InMemoryRunner
from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin
from google.adk.tools import AgentTool

from retailwiz.agent import create_retailwiz_root_agent, global_instructions
from retailwiz.subagents.google_search_agent import (
    google_product_search_agent_loop,
    google_product_search_agent_sequential,
    google_product_search_agent_standalone_w_output_schema,
    google_product_search_agent_standalone_wo_output_schema
)

# Test Configuration
# Test Configuration
# Test Configuration
QUERIES = [
    "iphone 16 pro max price in india",
    "best running shoes under 5000 rupees",
    "samsung s24 ultra vs pixel 9 pro comparison",
    "reviews for sony wh-1000xm5",
    "current trends in indian ethnic wear market",
    "technical specifications of ps5 slim",
    "where to buy framework laptop in india",
    "best deals on 55 inch 4k tv",
    "upcoming electric scooters in india 2025",
    "top rated whey protein brands",
    "dior bags in India",
    "Michael Kors vs. Coach vs. Tory Burch"
]

AGENTS = {
    "LoopAgent": google_product_search_agent_loop,
    "SequentialAgent": google_product_search_agent_sequential,
    "Standalone_Schema": google_product_search_agent_standalone_w_output_schema,
    "Standalone_NoSchema": google_product_search_agent_standalone_wo_output_schema
}

ITERATIONS = 28

def calculate_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"Mean": 0, "P5": 0, "P50": 0, "P95": 0, "P99": 0}
    
    values.sort()
    n = len(values)
    
    def get_percentile(p):
        k = (n - 1) * p
        f = int(k)
        c = k - f
        if f + 1 < n:
            return values[f] * (1 - c) + values[f + 1] * c
        else:
            return values[f]

    return {
        "Mean": sum(values) / n,
        "P5": get_percentile(0.05),
        "P50": get_percentile(0.50),
        "P95": get_percentile(0.95),
        "P99": get_percentile(0.99)
    }

async def run_benchmark():
    # Setup Output Directory and Files
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.dirname(__file__), "benchmark_outputs")
    os.makedirs(output_dir, exist_ok=True)
    
    csv_filename = os.path.join(output_dir, f"benchmark_{timestamp}.csv")
    jsonl_filename = os.path.join(output_dir, f"benchmark_{timestamp}.jsonl")
    stats_filename = os.path.join(output_dir, f"benchmark_stats_{timestamp}.csv")
    
    # Initialize CSV with headers
    fieldnames = ["Agent", "Query", "Iteration", "Success", "Latency", "Valid_JSON", "Product_Count", "Error"]
    with open(csv_filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
    # Clear outputs file (create empty file)
    with open(jsonl_filename, "w") as f:
        pass

    print(f"Starting Benchmark: {len(QUERIES)} queries x {len(AGENTS)} agents x {ITERATIONS} iterations")
    print(f"Saving results to:\n  CSV: {csv_filename}\n  JSONL: {jsonl_filename}")
    
    all_results = []

    for agent_name, search_agent in AGENTS.items():
        if shutdown_requested:
            print("\n🛑 Shutdown requested. Saving partial results...")
            break
            
        print(f"\n--- Testing Agent: {agent_name} ---")
        
        # Run the search agent DIRECTLY as the root agent to capture raw JSON output and metrics
        app = App(
            name=f"retailwiz_{agent_name}",
            root_agent=search_agent,
            plugins=[
                GlobalInstructionPlugin(global_instruction=global_instructions)
            ]
        )
        
        runner = InMemoryRunner(app=app)
        
        for query in QUERIES:
            if shutdown_requested:
                break
                
            print(f"  Query: {query}")
            for i in range(ITERATIONS):
                if shutdown_requested:
                    break
                start_time = time.time()
                success = False
                valid_json = False
                product_count = 0
                error_msg = ""
                text_content = ""
                
                # Use a consistent session ID for this agent's benchmark run
                session_id = f"benchmark_session_{agent_name}"
                
                try:
                    async with runner:
                        # Create session
                        await runner.session_service.create_session(
                            app_name=app.name,
                            user_id="benchmark_user",
                            session_id=session_id
                        )

                        # InMemoryRunner.run returns a generator of events
                        events = runner.run(
                            user_id="benchmark_user",
                            session_id=session_id,
                            new_message=types.Content(
                                role="user",
                                parts=[types.Part(text=query)]
                            )
                        )
                        
                        # Iterate through events to get the final response
                        final_response = None
                        for event in events:
                            final_response = event
                        
                        response = final_response
                        
                    latency = time.time() - start_time
                    success = True
                    
                    # Analyze Response
                    content = response.content
                    raw_content = ""
                    
                    # Extract text content
                    try:
                        if content and content.parts:
                            for part in content.parts:
                                if hasattr(part, 'text') and part.text:
                                    raw_content += part.text
                    except Exception as e:
                        print(f"    Warning: Error extracting text content: {e}")

                    # Try to parse JSON
                    try:
                        # Clean up markdown code blocks if present
                        clean_content = raw_content.strip()
                        if clean_content.startswith("```json"):
                            clean_content = clean_content[7:]
                        if clean_content.startswith("```"):
                            clean_content = clean_content[3:]
                        if clean_content.endswith("```"):
                            clean_content = clean_content[:-3]
                        
                        data = json.loads(clean_content)
                        valid_json = True  # JSON parsed successfully
                        
                        # Handle products: could be list, None, or missing
                        if "products" in data and data["products"] is not None:
                            product_count = len(data["products"])
                        else:
                            product_count = 0  # None or missing products is valid (e.g., market analysis queries)
                        
                        # Check for error field in response
                        if "error" in data:
                            error_msg = data["error"]

                    except json.JSONDecodeError as e:
                        error_msg = "Invalid JSON"
                    except Exception as e:
                        error_msg = f"Parse Error: {str(e)}"

                    # Save full output for debugging
                    output_entry = {
                        "agent": agent_name,
                        "query": query,
                        "iteration": i + 1,
                        "latency": latency,
                        "product_count": product_count,
                        "error": error_msg,
                        "raw_content": raw_content  # Capture raw content
                    }
                    
                    # Write to JSONL
                    with open(jsonl_filename, 'a') as f:
                        f.write(json.dumps(output_entry) + "\n")

                    # Write to CSV
                    with open(csv_filename, 'a', newline='') as f:
                        writer = csv.writer(f)
                        # Truncate raw_content for CSV readability, but keep enough to see the start
                        truncated_content = (raw_content[:500] + '...') if len(raw_content) > 500 else raw_content
                        writer.writerow([agent_name, query, i + 1, f"{latency:.2f}", product_count, error_msg, truncated_content])
                    
                    print(f"    Iter {i+1}: {'✅' if valid_json else '❌'} ({latency:.2f}s) - Products: {product_count}{' - Error: ' + error_msg if error_msg else ''}")


                except Exception as e:
                    latency = time.time() - start_time
                    error_msg = str(e)
                    success = False
                    valid_json = False
                    print(f"    Iter {i+1}: ❌ ({latency:.2f}s) - Exception: {error_msg}")
                finally:
                    # Clean up session to ensure fresh state for next iteration
                    try:
                        if hasattr(runner.session_service, 'delete_session'):
                             await runner.session_service.delete_session(
                                app_name=app.name,
                                user_id="benchmark_user",
                                session_id=session_id
                            )
                    except Exception as cleanup_error:
                        pass  # Silently handle cleanup errors

                
                result = {
                    "Agent": agent_name,
                    "Query": query,
                    "Iteration": i + 1,
                    "Success": success,
                    "Latency": latency,
                    "Valid_JSON": valid_json,
                    "Product_Count": product_count,
                    "Error": error_msg
                }
                all_results.append(result)

    # Calculate and Save Stats
    stats = []
    for agent_name in AGENTS.keys():
        agent_results = [r for r in all_results if r["Agent"] == agent_name]
        latencies = [r["Latency"] for r in agent_results if r["Success"]]
        product_counts = [r["Product_Count"] for r in agent_results if r["Success"]]
        
        latency_stats = calculate_stats(latencies)
        product_stats = calculate_stats(product_counts)
        
        stats.append({
            "Agent": agent_name,
            "Metric": "Latency",
            **latency_stats
        })
        stats.append({
            "Agent": agent_name,
            "Metric": "Product_Count",
            **product_stats
        })
        
    with open(stats_filename, "w", newline="") as f:
        fieldnames = ["Agent", "Metric", "Mean", "P5", "P50", "P95", "P99"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stats)

    print(f"\nBenchmark Complete.\nResults: {csv_filename}\nOutputs: {jsonl_filename}\nStats: {stats_filename}")

if __name__ == "__main__":
    # Register signal handler for graceful Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(run_benchmark())
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
