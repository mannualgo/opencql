from lark import Transformer

class CQLCompiler(Transformer):
    """
    Transforms the Lark Parse Tree into a structured Query Plan (AST).
    """
    def query(self, args):
        # args[0] -> column name
        # args[1] -> model name
        # args[2] -> clauses (list of tuples), if present
        
        plan = {
            "type": "SELECT",
            "target": str(args[0]),
            "model": str(args[1]),
            "steps": {}
        }
        
        # If we have clauses (args length > 2), process them
        if len(args) > 2:
            # args[2] is now a simple list of tuples like [('system', {...}), ('knowledge', {...})]
            # because of the 'clauses' method below.
            for step_type, step_data in args[2]:
                plan["steps"][step_type] = step_data
                
        return plan

    # --- Structural Helpers (The Fix) ---
    def clauses(self, args):
        """Passes the list of clauses up as a Python list."""
        return args

    def clause(self, args):
        """Unwraps the single child from the clause rule."""
        return args[0]

    # --- Clause Handlers ---
    def with_system(self, args):
        return ("system", dict(args[0]))

    def join_knowledge(self, args):
        return ("knowledge", dict(args[0]))
    
    def group_by(self, args):
        return ("group_by", {"column": str(args[0]), "partitions": args[1]})

    def aggregate_with(self, args):
        return ("aggregate", args[0])

    def inject_history(self, args):
        return ("history", args[0])

    # --- Primitives ---
    def kv_list(self, args):
        return args

    def kv_pair(self, args):
        return (str(args[0]), args[1])

    def value_list(self, args):
        return args

    def value(self, args):
        val = args[0]
        # Check if it is a Token (ESCAPED_STRING, SIGNED_NUMBER, or STRING)
        if hasattr(val, 'type'):
            if val.type == 'STRING': # Matches 'text' or "text"
                return val[1:-1]
            if val.type == 'ESCAPED_STRING': # Matches "text"
                return val[1:-1]
        return val

    def variable(self, args):
        return {"_param": str(args[0])}
    
    # --- Basic Terminals ---
    # These helpers ensure tokens are converted to simple strings
    def column(self, args):
        return str(args[0])
    
    def model(self, args):
        return str(args[0])
    def start(self, args):
        # Unwrap the 'statement' rule
        return args[0]