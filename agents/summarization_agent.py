# /agentic-ai-system/agents/summarization_agent.py

from agents.base_agent import BaseAgent
import time
import random

class SummarizationAgent(BaseAgent):
    """
    An agent that simulates summarizing a given piece of text.
    """
    def __init__(self):
        super().__init__(agent_name="summarization", task_stream="tasks:summarization")

    def _perform_task(self, task_data: dict) -> dict:
        text_to_summarize = task_data.get('text')
        if not text_to_summarize:
            raise ValueError("Text not provided for summarization.")

        self.logger.info("Performing summarization...")
        # Simulate LLM processing time
        time.sleep(random.uniform(2, 4))
        
        # In a real implementation, you would call an LLM API (e.g., OpenAI, Anthropic)
        # with a prompt to summarize the text.
        
        summary = f"Summary: The main point of the text is that Paris is the capital of France."
        
        return {"summary": summary}

if __name__ == '__main__':
    # This allows running the agent as a standalone script
    from utils import setup_logging
    setup_logging()
    agent = SummarizationAgent()
    agent.run()