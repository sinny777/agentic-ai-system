from agents.base_agent import BaseAgent
import time

class ClaimApprovalAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="claim_approval", task_stream="tasks:claim_approval", tool_name="approval_rules_engine")

    def _perform_task(self, task_data: dict) -> dict:
        self.logger.info(f"Making final decision on claim...")
        
        # These values are resolved and passed by the orchestrator
        policy_status = task_data.get('policy_status')
        fraud_score = float(task_data.get('fraud_score', 0))
        
        decision = "Rejected" # Default
        if policy_status == "Covered" and fraud_score < 0.7:
            decision = "Approved"
        elif policy_status == "Covered" and fraud_score >= 0.7:
            decision = "Manual Review (High Fraud Score)"
        elif policy_status == "Not Covered":
            decision = "Rejected (Not Covered by Policy)"
            
        return {"final_decision": decision, "reason": f"Policy: {policy_status}, Fraud Score: {fraud_score}"}