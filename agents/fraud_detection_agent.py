from agents.base_agent import BaseAgent
import time, ast

class FraudDetectionAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="fraud_detection", task_stream="tasks:fraud_detection", tool_name="fraud_model")

    def _perform_task(self, task_data: dict) -> dict:
        self.logger.info(f"\n\n>>>Performing fraud detection task with data: \n{task_data}\n\n")
        claim_details = task_data.get('claim_details')
        try:
            claim_details = ast.literal_eval(claim_details)
        except (ValueError, SyntaxError) as e:
            self.logger.error(f"In FraudDetectionAgent, could not parse claim_details: {claim_details}. Error: {e}")
            raise
        self.logger.info(f"Analyzing claim for fraud...")
        time.sleep(1.5)
        
        # Simple fraud rule: flag if claim is over $1000
        fraud_score = 0.85 if claim_details['total_billed'] > 1000 else 0.15
        result = {"fraud_score": fraud_score, "is_flagged": fraud_score > 0.7}
        self.logger.info(f"Fraud Detection Result: {result}")
        return result