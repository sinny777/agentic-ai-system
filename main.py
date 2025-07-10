# /agentic-ai-system/insurance_main.py

import multiprocessing, time, logging, json
from agents.planner_agent import PlannerAgent
from agents.document_reader_agent import DocumentReaderAgent
from agents.policy_check_agent import PolicyCheckAgent
from agents.fraud_detection_agent import FraudDetectionAgent
from agents.claim_approval_agent import ClaimApprovalAgent
from orchestrator import Orchestrator
from utils import setup_logging
from redis_client import get_redis_client
import governance

def run_agent(agent_class):
    setup_logging()
    agent_class().run()

def run_orchestrator():
    setup_logging()
    time.sleep(2) # Give agents time to create streams
    Orchestrator().run()

def setup_environment(redis_client):
    """Clears old data and sets up initial state for the demo."""
    logger = logging.getLogger("Setup")
    logger.info("--- Setting up environment for insurance claim demo ---")
    
    # 1. Clear old data
    keys_to_delete = redis_client.keys('job:*') + redis_client.keys('tasks:*') + \
                     redis_client.keys('results:*') + redis_client.keys('errors:*') + \
                     ["registered_agents", "gov:permissions", "policies"]
    if keys_to_delete:
        redis_client.delete(*keys_to_delete)
    
    # 2. Setup Governance Rules
    governance.register_tool_access("document_reader", ["ocr_tool"])
    governance.register_tool_access("policy_check", ["policy_api"])
    governance.register_tool_access("fraud_detection", ["fraud_model"])
    governance.register_tool_access("claim_approval", ["approval_rules_engine"])

    # 3. Setup Mock Data (Customer Policy)
    policy_data = {
        "policyholder": "John Doe",
        "is_active": True,
        "post_hospital_limit": 5000.00
    }
    redis_client.hset("policies", "policy-12345", json.dumps(policy_data))
    logger.info("Environment setup complete.")


if __name__ == "__main__":
    setup_logging()
    
    redis_client = get_redis_client()
    setup_environment(redis_client)

    agents_to_run = [
        DocumentReaderAgent, PolicyCheckAgent, FraudDetectionAgent, ClaimApprovalAgent
    ]

    processes = [multiprocessing.Process(target=run_agent, args=(agent,)) for agent in agents_to_run]
    processes.append(multiprocessing.Process(target=run_orchestrator))

    for p in processes:
        p.start()

    time.sleep(3) # Let processes initialize

    # --- Create and start the insurance claim job ---
    planner = PlannerAgent()
    
    # This is the incoming claim data
    claim_data = {
        "claim_id": "claim-abc-789",
        "policy_id": "policy-12345",
        "claimant_name": "John Doe",
        "documents": ["bill.pdf", "receipt.pdf"]
    }
    
    goal = f"Process post-hospitalization claim {claim_data['claim_id']} for {claim_data['claimant_name']}."
    plan = planner.create_insurance_plan(goal=goal, claim_data=claim_data)

    # Manually kickstart the job
    Orchestrator().start_new_job(plan)

    logging.info(f"Job {plan['job_id']} kicked off. System is running.")
    logging.info("Monitor logs to see the workflow. Press Ctrl+C to terminate.")

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        logging.info("Shutting down processes.")
        for p in processes:
            p.terminate()
            p.join()