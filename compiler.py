from lark import Transformer

class CQLCompiler(Transformer):
    """
    Transforms the Lark Parse Tree into a structured Query Plan (AST).
    """
    def query(self, args):
        plan = {
            "type": "SELECT",
            "target": str(args[0].children[0]),
            "model": str(args[1].children[0]),
            "steps": {}
        }
        if len(args) > 2:
            for step_type, step_data in args[2].children:
                plan["steps"][step_type] = step_data
        return plan

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

    def kv_list(self, args):
        return args

    def kv_pair(self, args):
        return (str(args[0]), args[1])

    def value_list(self, args):
        return args

    def value(self, args):
        val = args[0]
        if hasattr(val, 'type') and val.type == 'ESCAPED_STRING':
            return val[1:-1]
        return val

    def variable(self, args):
        return {"_param": str(args[0])}
