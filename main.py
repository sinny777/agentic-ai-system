import multiprocessing
import time
import logging

from agents.planner_agent import PlannerAgent
from agents.web_search_agent import WebSearchAgent
from agents.summarization_agent import SummarizationAgent
from orchestrator import Orchestrator
from utils import setup_logging
from redis_client import get_redis_client

def run_agent(agent_class):
    """Target function to run an agent in a separate process."""
    setup_logging()
    agent = agent_class()
    agent.run()

def run_orchestrator():
    """Target function to run the orchestrator."""
    setup_logging()
    orchestrator = Orchestrator()
    # A bit of a hack: give agents time to create their streams before orchestrator listens
    time.sleep(2)
    orchestrator.run()


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger("Main")

    # Clear previous run data from Redis for a clean start
    redis_client = get_redis_client()
    logger.info("Clearing old data from Redis...")
    for key in redis_client.scan_iter("job:*"):
        redis_client.delete(key)
    for key in redis_client.scan_iter("tasks:*"):
        redis_client.delete(key)
    for key in redis_client.scan_iter("results:*"):
        redis_client.delete(key)
    for key in redis_client.scan_iter("errors:*"):
        redis_client.delete(key)
    redis_client.delete("registered_agents")


    # Define the agents and orchestrator to run
    processes = {
        "WebSearchAgent": multiprocessing.Process(target=run_agent, args=(WebSearchAgent,)),
        "SummarizationAgent": multiprocessing.Process(target=run_agent, args=(SummarizationAgent,)),
        "Orchestrator": multiprocessing.Process(target=run_orchestrator)
    }

    # Start all processes
    for name, p in processes.items():
        logger.info(f"Starting process: {name}")
        p.start()

    logger.info("All services started. Waiting a moment before creating a plan...")
    time.sleep(3) # Give processes time to initialize

    # --- Create and start a new job ---
    planner = PlannerAgent()
    goal = "Find the capital of France and provide a summary of the search results."
    plan = planner.create_plan(goal=goal)

    # The orchestrator will see the new job and start dispatching tasks
    # We can simulate this by directly calling a method on a local orchestrator instance
    # In a real distributed system, the orchestrator would discover this new job itself.
    
    # For this example, we'll give the main orchestrator process the plan.
    # A simple way to do this is to have the orchestrator periodically check for new jobs.
    # We will manually kickstart the first job for this example.
    
    local_orchestrator = Orchestrator()
    local_orchestrator.start_new_job(plan)

    logger.info(f"Job {plan['job_id']} kicked off. The system is now running.")
    logger.info("Monitor the logs of the individual processes to see the workflow.")
    logger.info("Press Ctrl+C to terminate.")

    try:
        # Keep the main process alive to monitor
        for p in processes.values():
            p.join()
    except KeyboardInterrupt:
        logger.info("Termination signal received. Shutting down processes.")
        for name, p in processes.items():
            logger.info(f"Terminating {name}...")
            p.terminate()
            p.join()
        logger.info("All processes terminated.")