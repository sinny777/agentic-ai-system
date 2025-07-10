from agents.base_agent import BaseAgent
import time, json

class DocumentReaderAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="document_reader", task_stream="tasks:document_reader", tool_name="ocr_tool")

    def _perform_task(self, task_data: dict) -> dict:
        claim_data = json.loads(task_data.get('claim_data'))
        self.logger.info(f"Reading documents for claim {claim_data['claim_id']}...")
        time.sleep(2) # Simulate OCR processing
        
        # Mocked result of document reading
        extracted_data = {
            "patient_name": claim_data['claimant_name'],
            "total_billed": 1500.00,
            "procedures": ["Medication", "Consultation"],
            "hospital_name": "General Hospital"
        }
        return {"extracted_data": extracted_data}