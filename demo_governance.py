from runtime import CQLRuntime

query = """
SELECT report 
FROM llama3
JOIN KNOWLEDGE (source='company_docs', threshold=0.8)
GROUP BY domain ('Legal', 'Financial')
AGGREGATE WITH 'Summary'
"""

runtime = CQLRuntime()
result = runtime.execute(query)
print("\nFinal Output:", result)
