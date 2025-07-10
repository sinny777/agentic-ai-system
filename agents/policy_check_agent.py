from agents.base_agent import BaseAgent
import time, json, ast

from utils import robust_string_to_dict

class PolicyCheckAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="policy_check", task_stream="tasks:policy_check", tool_name="policy_api")

    def _perform_task(self, task_data: dict) -> dict:
        self.logger.info(f"\n\n>>>> Performing policy check task with data: \n{task_data}\n\n")
        # policy_data = json.loads(task_data.get('claim_data'))
        # Extract policy_id and claim_details from task_data
        policy_id = task_data.get('policy_id')
        claim_details = task_data.get('claim_details') # This will be passed from the orchestrator
        claim_details = robust_string_to_dict(claim_details)
        self.logger.info(f"Checking policy {policy_id} against claim details...")
        
        policy_data_str = self.redis_client.hget("policies", policy_id)
        policy_data = robust_string_to_dict(policy_data_str)
        
        time.sleep(1)
        # self.logger.debug(f"Policy Data: {policy_data}, Claim Details: {claim_details}")
        is_covered = policy_data['is_active'] and claim_details['total_billed'] <= policy_data['post_hospital_limit']
        
        return {
            "policy_verdict": "Covered" if is_covered else "Not Covered",
            "coverage_limit": policy_data['post_hospital_limit']
        }