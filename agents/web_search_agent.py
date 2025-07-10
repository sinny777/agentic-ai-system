
from agents.base_agent import BaseAgent
import time
import random

class WebSearchAgent(BaseAgent):
    """
    An agent that simulates performing a web search for a given query.
    """
    def __init__(self):
        super().__init__(agent_name="web_search", task_stream="tasks:web_search")

    def _perform_task(self, task_data: dict) -> dict:
        query = task_data.get('query')
        if not query:
            raise ValueError("Query not provided for web search.")

        self.logger.info(f"Performing web search for: '{query}'")
        # Simulate network latency and work
        time.sleep(random.uniform(1, 3))
        
        # In a real implementation, you would use a library like `requests`
        # and `BeautifulSoup` or call a search API (e.g., Google, Bing, Serper).
        
        mock_result = f"Search results for '{query}': The capital of France is Paris. Wikipedia also mentions Lyon and Marseille."
        
        return {"content": mock_result}

if __name__ == '__main__':
    # This allows running the agent as a standalone script
    from utils import setup_logging
    setup_logging()
    agent = WebSearchAgent()
    agent.run()