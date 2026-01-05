import json
import statistics

def analyze_meaningfulness(file_path):
    stats = {
        'Standalone_NoSchema': {'total': 0, 'meaningful': 0, 'meaningful_reasons': {'products': 0, 'text_only': 0}},
        'Standalone_Schema': {'total': 0, 'meaningful': 0, 'meaningful_reasons': {'products': 0, 'text_only': 0}},
        'SequentialAgent': {'total': 0, 'meaningful': 0, 'meaningful_reasons': {'products': 0, 'text_only': 0}},
        'LoopAgent': {'total': 0, 'meaningful': 0, 'meaningful_reasons': {'products': 0, 'text_only': 0}}
    }

    TEXT_THRESHOLD = 150  # Characters. Below this is likely an error message or "I cannot answer".

    with open(file_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            agent = entry.get('agent')
            
            if agent not in stats:
                continue
                
            stats[agent]['total'] += 1
            
            is_meaningful = False
            reason = None
            
            # Check 1: Products found
            if entry.get('product_count', 0) > 0:
                is_meaningful = True
                reason = 'products'
            
            # Check 2: Rich Text Content (even if 0 products)
            # We need to extract the actual text length, ignoring JSON overhead if possible
            raw = entry.get('raw_content', '')
            content_len = len(raw) if raw else 0
            
            # Heuristic: If parsing as JSON works, check 'answer' field length
            # If parsing fails, check raw length
            answer_text = ""
            try:
                json_content = json.loads(raw)
                if isinstance(json_content, dict):
                    answer_text = json_content.get('answer', '')
                    if not answer_text and isinstance(json_content, str): # Double encoded? 
                         # Sometimes raw_content is a JSON string of a JSON object? 
                         # But usually it's just the string.
                         pass
                else:
                    # raw_content might be just a string (for NoSchema)
                    answer_text = raw
            except:
                # If invalid JSON, treat whole raw content as text
                answer_text = raw

            if not is_meaningful:
                if len(answer_text) > TEXT_THRESHOLD:
                    is_meaningful = True
                    reason = 'text_only'
            
            if is_meaningful:
                stats[agent]['meaningful'] += 1
                stats[agent]['meaningful_reasons'][reason] += 1

    print(f"{'AGENT':<25} | {'TOTAL':<5} | {'MEANINGFUL':<10} | {'%':<6} | {'(Products)':<10} | {'(Text Only)':<10}")
    print("-" * 80)
    for agent, data in stats.items():
        if data['total'] == 0: continue
        pct = (data['meaningful'] / data['total']) * 100
        print(f"{agent:<25} | {data['total']:<5} | {data['meaningful']:<10} | {pct:<5.1f}% | {data['meaningful_reasons']['products']:<10} | {data['meaningful_reasons']['text_only']:<10}")

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else '/usr/local/google/home/sanjitmehta/work/google-adk-samples/retailwiz/benchmark_outputs/benchmark_20260102_125142.jsonl'
    analyze_meaningfulness(file_path)
