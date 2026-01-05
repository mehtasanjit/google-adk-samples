import json
import sys
import re
from collections import defaultdict
import difflib

def load_data(file_path):
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return data

def extract_products_list(entry):
    """
    Robustly extracts the 'products' list from an entry, handling:
    1. Top-level 'products' field (already parsed).
    2. 'raw_content' as a dict (already parsed).
    3. 'raw_content' as a string (needs JSON parsing).
    4. 'raw_content' as a markdown code block (needs regex + JSON parsing).
    """
    # 1. Try top-level products
    products = entry.get('products')
    if products and isinstance(products, list):
        return products

    raw_content = entry.get('raw_content')
    if not raw_content:
        return []

    parsed_content = None

    # 2. Check if raw_content is already a dict
    if isinstance(raw_content, dict):
        parsed_content = raw_content

    # 3. If string, try to parse it
    elif isinstance(raw_content, str):
        # Clean up common issues if necessary
        content_str = raw_content.strip()
        
        # Try direct JSON parse
        try:
            parsed_content = json.loads(content_str)
        except json.JSONDecodeError:
            # 4. Try regex for markdown code blocks
            # Match ```json ... ``` or just { ... } if it looks like JSON but wasn't valid directly (maybe extra chars?)
            # Usually it's the markdown wrapper that causes issues.
            match = re.search(r'```json\s*(\{.*?\})\s*```', content_str, re.DOTALL)
            if not match:
                match = re.search(r'```\s*(\{.*?\})\s*```', content_str, re.DOTALL)
            
            if match:
                try:
                    parsed_content = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            else:
                 # Fallback: try to find start/end of JSON object
                 # This is risky but useful for "Text... {json} ...Text"
                 try:
                     start = content_str.find('{')
                     end = content_str.rfind('}')
                     if start != -1 and end != -1:
                         candidate = content_str[start:end+1]
                         parsed_content = json.loads(candidate)
                 except json.JSONDecodeError:
                     pass

    if parsed_content and isinstance(parsed_content, dict):
        return parsed_content.get('products', [])
    
    return []

def get_product_names(entry):
    products = extract_products_list(entry)
    names = []
    if not products:
        return []
        
    for p in products:
        if isinstance(p, dict) and p.get('name'):
            names.append(p['name'].lower().strip())
    return names

def analyze_schema_vs_noschema(file_path):
    data = load_data(file_path)
    
    # Group by query and agent
    query_agent_data = defaultdict(lambda: defaultdict(list))
    
    for entry in data:
        query = entry.get('query')
        agent = entry.get('agent')
        query_agent_data[query][agent].append(entry)

    print(f"{'Query':<40} | {'Schema Prod':<11} | {'NoSchema Prod':<13} | {'Seq Prod':<8} | {'Notes'}")
    print("-" * 120)

    for query, agents in query_agent_data.items():
        schema_entries = agents.get('Standalone_Schema', [])
        noschema_entries = agents.get('Standalone_NoSchema', [])
        seq_entries = agents.get('SequentialAgent', [])

        # Flatten products for each agent to get a "Union" of what they found across iterations
        schema_products = set()
        for e in schema_entries:
            schema_products.update(get_product_names(e))
            
        noschema_products = set()
        for e in noschema_entries:
            noschema_products.update(get_product_names(e))
            
        seq_products = set()
        for e in seq_entries:
            seq_products.update(get_product_names(e))

        # Check for hallucinations: Products in Schema that are NOT in Sequential (Reference)
        unique_to_schema = []
        for sp in schema_products:
            match = False
            for seq_p in seq_products:
                # Fuzzy match
                if sp in seq_p or seq_p in sp or difflib.SequenceMatcher(None, sp, seq_p).ratio() > 0.6:
                    match = True
                    break
            if not match:
                unique_to_schema.append(sp)

        # Output stats
        avg_schema = sum(len(get_product_names(e)) for e in schema_entries) / len(schema_entries) if schema_entries else 0
        
        # Calculate avg based on the NEW robust extraction
        noschema_counts = [len(get_product_names(e)) for e in noschema_entries]
        avg_noschema = sum(noschema_counts) / len(noschema_entries) if noschema_entries else 0
        
        seq_counts = [len(get_product_names(e)) for e in seq_entries]
        avg_seq = sum(seq_counts) / len(seq_entries) if seq_entries else 0

        print(f"{query[:38]:<40} | {avg_schema:<11.1f} | {avg_noschema:<13.1f} | {avg_seq:<8.1f} |")
        
        if unique_to_schema:
             print(f"  [POTENTIAL HALLUCINATION] Schema found ({len(unique_to_schema)}) unique: {unique_to_schema[:3]}...")
        
        # Divergence check specifically for "0 vs Many"
        if avg_schema > 0 and avg_noschema == 0:
             print(f"  [DIVERGENCE] Schema found products, NoSchema found NONE.")
             
        if avg_seq == 0 and avg_schema > 0:
             print(f"  [DIVERGENCE] Sequential found NONE, but Schema found products.")

        print("-" * 120)

if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else '/usr/local/google/home/sanjitmehta/work/google-adk-samples/retailwiz/benchmark_outputs/benchmark_20260104_163537.jsonl'
    analyze_schema_vs_noschema(file_path)
