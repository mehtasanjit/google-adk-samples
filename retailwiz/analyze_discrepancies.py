import json
import sys

def analyze_benchmarks(file_path):
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))

    # Group by query
    queries = {}
    for entry in data:
        q = entry['query']
        if q not in queries:
            queries[q] = {}
        queries[q][entry['agent']] = entry

    print(f"Analyzing {len(queries)} unique queries...\n")

    for q, agents in queries.items():
        seq = agents.get('SequentialAgent')
        no_schema = agents.get('Standalone_NoSchema')

        if not seq or not no_schema:
            continue

        # Check if Sequential "failed" (Error or Empty Answer with 0 products)
        seq_failed = False
        seq_reason = ""
        
        # Parse Sequential Content
        seq_content = seq.get('raw_content', '')
        seq_answer = ""
        try:
            if seq_content:
                seq_json = json.loads(seq_content)
                seq_answer = seq_json.get('answer', '')
        except:
            pass

        if seq.get('error'):
            seq_failed = True
            seq_reason = f"Error: {seq['error']}"
        elif seq['product_count'] == 0 and (not seq_answer or len(seq_answer) < 50):
            # refined check: valid failure if answer is also short/empty
            seq_failed = True
            seq_reason = "0 Products & Short/Empty Answer"

        # Check if NoSchema "succeeded" (Has detailed content)
        ns_succeeded = False
        ns_content = no_schema.get('raw_content', '')
        
        # Simple heuristic for "content present"
        if len(ns_content) > 100: 
            ns_succeeded = True

        print(f"Query: {q}")
        print(f"  Sequential: Products={seq['product_count']}, AnswerLen={len(seq_answer)}, Error={seq.get('error', '')}")
        print(f"  Standalone: Products={no_schema['product_count']}, ContentLen={len(ns_content)}, Error={no_schema.get('error', '')}")
        
        if seq['product_count'] == 0 and len(seq_answer) < 50 and len(ns_content) > 100:
             print("  *** DISCREPANCY FOUND ***")
        print("-" * 30)

if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else '/usr/local/google/home/sanjitmehta/work/google-adk-samples/retailwiz/benchmark_outputs/benchmark_20260102_125142.jsonl'
    analyze_benchmarks(file_path)
