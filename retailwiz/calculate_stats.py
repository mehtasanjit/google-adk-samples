import csv
import sys
import os
from typing import List, Dict

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

def main():
    if len(sys.argv) < 2:
        print("Usage: python calculate_stats.py <csv_file>")
        sys.exit(1)
        
    csv_file = sys.argv[1]
    output_file = csv_file.replace(".csv", "_stats.csv")
    
    results = []
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)
            
    agents = set(r["Agent"] for r in results)
    stats = []
    
    for agent_name in agents:
        agent_results = [r for r in results if r["Agent"] == agent_name]
        
        # Latency (only for successful runs)
        latencies = [float(r["Latency"]) for r in agent_results if r["Success"] == "True"]
        
        # Product Count (only for successful runs)
        product_counts = [int(r["Product_Count"]) for r in agent_results if r["Success"] == "True"]
        
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
        
    with open(output_file, "w", newline="") as f:
        fieldnames = ["Agent", "Metric", "Mean", "P5", "P50", "P95", "P99"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stats)
        
    print(f"Stats saved to {output_file}")
    
    # Print stats to console
    print(f"\nStats for {csv_file}:")
    for row in stats:
        print(f"{row['Agent']} - {row['Metric']}: Mean={row['Mean']:.2f}, P50={row['P50']:.2f}, P95={row['P95']:.2f}, P99={row['P99']:.2f}")

if __name__ == "__main__":
    main()
