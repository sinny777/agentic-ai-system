# /agentic-ai-system/agents/planner_agent.py

import json
import logging
from redis_client import get_redis_client
from utils import generate_job_id

class PlannerAgent:
    """
    Creates a plan to achieve a high-level goal. In a real system, this
    would involve an LLM call to generate a structured plan (e.g., JSON).
    """
    def __init__(self):
        self.logger = logging.getLogger("PlannerAgent")
        self.redis_client = get_redis_client()

    def create_plan(self, goal: str) -> dict:
        """
        Generates a job and a plan. Mocks an LLM call.
        """
        self.logger.info(f"Creating a plan for the goal: '{goal}'")
        job_id = generate_job_id()

        # Mocked LLM response: A JSON plan based on the goal.
        # This defines tasks, the agent responsible, and dependencies.
        # An empty dependency list means the task can start immediately.
        plan = {
            "job_id": job_id,
            "goal": goal,
            "tasks": [
                {
                    "task_id": "task1",
                    "agent": "web_search",
                    "details": {"query": "Capital of France"},
                    "dependencies": []
                },
                {
                    "task_id": "task2",
                    "agent": "summarization",
                    "details": {"text": "result_from:task1"}, # Placeholder for data dependency
                    "dependencies": ["task1"]
                }
            ]
        }
        
        # Store the plan in Redis so the orchestrator can access it
        self.redis_client.hset(f"job:{job_id}", "plan", json.dumps(plan))
        self.redis_client.hset(f"job:{job_id}", "status", "pending")
        
        self.logger.info(f"Plan created for job {job_id}.")
        return plan