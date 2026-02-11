from opencql.runtime import CQLRuntime

# The Experiment: A Governance Query
query = """
SELECT compliance_report 
FROM gpt_4_turbo 
WITH SYSTEM (ROLE='Auditor')
JOIN KNOWLEDGE (source='audit_logs', threshold=0.9)
GROUP BY domain ('GDPR', 'HIPAA', 'SOC2')
AGGREGATE WITH 'Executive_Summary'
"""

if __name__ == "__main__":
    runtime = CQLRuntime()
    result = runtime.execute(query)
    print(f"\n [Final Result]: {result}")
