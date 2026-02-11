from lark import Lark
from compiler import CQLCompiler
from vectors import VectorStore
from llm import OpenSourceLLM

# Load Grammar
import os
GRAMMAR_PATH = os.path.join(os.path.dirname(__file__), 'grammar.lark')
with open(GRAMMAR_PATH, 'r') as f:
    GRAMMAR = f.read()

class CQLRuntime:
    def __init__(self):
        self.parser = Lark(GRAMMAR, start='start', parser='lalr')
        self.compiler = CQLCompiler()
        self.vector_store = VectorStore()
        
        # Pre-load some dummy data for the JOIN
        self.vector_store.add_documents([
            {"id": 1, "text": "GDPR requires data encryption.", "domain": "Legal"},
            {"id": 2, "text": "The budget is $50k.", "domain": "Financial"},
            {"id": 3, "text": "Kubernetes cluster is ready.", "domain": "Technical"},
            {"id": 4, "text": "HIPAA compliance is mandatory.", "domain": "Legal"},
        ])

    def execute(self, query_code, params=None):
        params = params or {}
        
        # 1. Compile
        print("--- 1. Compiling Query ---")
        tree = self.parser.parse(query_code)
        plan = self.compiler.transform(tree)
        plan = self._resolve_params(plan, params)
        print(f"Plan: {plan}")

        # 2. Join Knowledge (Vector Retrieval)
        context_chunks = []
        if 'knowledge' in plan['steps']:
            source = plan['steps']['knowledge'].get('source')
            print(f"\n--- 2. Executing Semantic JOIN on '{source}' ---")
            results = self.vector_store.search("query", threshold=0.1) # Low threshold for demo
            context_chunks = [r[0] for r in results]
            print(f"Retrieved {len(context_chunks)} documents.")

        # 3. Semantic MapReduce (Group By)
        final_response = ""
        print ("plan['model']",plan['model'])
        llm = OpenSourceLLM(model_name=plan['model'])

        if 'group_by' in plan['steps']:
            gb_col = plan['steps']['group_by']['column']
            partitions = plan['steps']['group_by']['partitions']
            
            print(f"\n--- 3. Starting MapReduce (Grouping by '{gb_col}') ---")
            map_results = []
            
            for group in partitions:
                # FILTER context for this group (The Map Phase)
                group_context = [doc['text'] for doc in context_chunks if doc.get(gb_col) == group]
                
                if group_context:
                    print(f"   > [MAP AGENT] Analyzing partition: '{group}' ({len(group_context)} docs)...")
                    prompt = f"Context: {group_context}\nAnalyze this specific domain."
                    response = llm.generate(prompt, system_prompt=f"You are an expert in {group}")
                    map_results.append(f"{group} Analysis: {response}")
                else:
                    print(f"   > [MAP AGENT] Partition '{group}' is empty. Skipping.")

            # The Reduce Phase
            print(f"\n--- 4. Reducing Results ---")
            agg_protocol = plan['steps'].get('aggregate', 'Concatenate')
            final_response = " | ".join(map_results)
        
        else:
            # Standard Execution
            final_response = llm.generate("Context: " + str(context_chunks))

        return final_response

    def _resolve_params(self, node, params):
        if isinstance(node, dict):
            if "_param" in node:
                return params.get(node["_param"], node["_param"])
            return {k: self._resolve_params(v, params) for k, v in node.items()}
        elif isinstance(node, list):
            return [self._resolve_params(x, params) for x in node]
        return node
