# /agentic-ai-system/agents/planner_agent.py

import json, logging
from redis_client import get_redis_client
from utils import generate_job_id

class PlannerAgent:
    def __init__(self):
        self.logger = logging.getLogger("PlannerAgent")
        self.redis_client = get_redis_client()

    def create_insurance_plan(self, goal: str, claim_data: dict) -> dict:
        self.logger.info(f"Creating insurance claim plan for goal: '{goal}'")
        job_id = generate_job_id()

        plan = {
            "job_id": job_id,
            "goal": goal,
            "tasks": [
                {
                    "task_id": "task1_read_docs",
                    "agent": "document_reader",
                    "details": {"claim_data": json.dumps(claim_data)},
                    "dependencies": []
                },
                {
                    "task_id": "task2_check_policy",
                    "agent": "policy_check",
                    "details": {
                        "policy_id": claim_data['policy_id'],
                        "claim_details": "data_from:task1_read_docs.extracted_data"
                    },
                    "dependencies": ["task1_read_docs"]
                },
                {
                    "task_id": "task3_check_fraud",
                    "agent": "fraud_detection",
                    "details": {
                        "claim_details": "data_from:task1_read_docs.extracted_data"
                    },
                    "dependencies": ["task1_read_docs"]
                },
                {
                    "task_id": "task4_approve_claim",
                    "agent": "claim_approval",
                    "details": {
                        "policy_status": "data_from:task2_check_policy.policy_verdict",
                        "fraud_score": "data_from:task3_check_fraud.fraud_score"
                    },
                    "dependencies": ["task2_check_policy", "task3_check_fraud"]
                }
            ]
        }
        
        self.redis_client.hset(f"job:{job_id}", "plan", json.dumps(plan))
        self.redis_client.hset(f"job:{job_id}", "status", "pending")
        
        self.logger.info(f"Plan created for job {job_id}.")
        return plan